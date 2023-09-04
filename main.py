import os
import string
from urllib.parse import urljoin
from random import choice

import aiohttp
import asyncio

from typing import Tuple, Generator

URL_2CH = 'https://2ch.hk/'
API_URL_2CH = f'https://2ch.hk/api/mobile/v2/'
FOLDER_NAME = '2ch_files'

def parse_url(url: str) -> Tuple[str, str]:
    url = url.strip().rstrip('.html')
    url_split =  url.split('/')
    try:
        board = url_split[-3]
        thread = url_split[-1]
    except IndexError:
        raise IndexError('Ссылка не корректная. Пример ссылки: https://2ch.life/b/res/292606618.html')

    return board, thread


def randomize_filename(name: str = '', length = 7) -> str:
    rand_part = ''.join(choice(string.ascii_letters + string.digits) for _ in range(length))
    return f'{rand_part}_{name}'


def extract_files_urls(resp_json: dict) -> list:
    file_urls = []
    for post in resp_json['posts']:
        if post.get('files') is not None:
            for file in post['files']:
                file_urls.append({
                    'name': randomize_filename(file['name']),
                    'url': urljoin(URL_2CH, file['path'])
                })
    return file_urls


async def download_file(session, url, save_path, update_progress: Generator):
    async with session.get(url) as response:
        if response.status == 200:
            with open(save_path, 'wb+') as file:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    file.write(chunk)
        else:
            print(f"Не удалось скачать файл {url}. Статус код: {response.status}")
    update_progress.send(1)


async def progress_updater(tasks: list):
    total_tasks_count = len(tasks)
    complied_tasks_count = len(list(filter(lambda cond: cond, [t.done() for t in tasks])))
    while complied_tasks_count < total_tasks_count:
        await asyncio.sleep(0.5)
        print(f"\rПрогресс: {complied_tasks_count}/{total_tasks_count}", end="", flush=True)
        complied_tasks_count = len(list(filter(lambda cond: cond, [t.done() for t in tasks])))

    print("\nЗагрузка завершена")


def task_finished_print(total_count: int):
    count = 0
    while count <= total_count:
        print(f"\rЗагрузка: {count}/{total_count}", end="", flush=True)
        _ = yield
        count += 1


async def main():
    thread_url = input('Введите URL треда: ')
    try:
        board, thread = parse_url(thread_url)
    except IndexError as e:
        print(str(e))
        return

    async with aiohttp.ClientSession() as session:
        get_posts_list_url = urljoin(API_URL_2CH, f'after/{board}/{thread}/{thread}')
        try:
            async with session.get(get_posts_list_url) as resp:
                resp_json = await resp.json()
                assert resp.status == 200, 'Не корректный ответ. Отсутствует список постов'
                assert resp_json.get('posts') is not None, 'Не корректный ответ. Отсутствует список постов'
        except (aiohttp.ClientError, AssertionError) as e:
            print(str(e))
            return

        file_urls = extract_files_urls(resp_json)
        folder_path = f'{FOLDER_NAME}_{board}_{thread}'
        os.makedirs(folder_path, exist_ok=True)

        gen = task_finished_print(len(file_urls))
        next(gen)

        await asyncio.gather(*[
            download_file(session, d['url'], os.path.join(folder_path, d['name']), gen) for d in file_urls
        ])

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())