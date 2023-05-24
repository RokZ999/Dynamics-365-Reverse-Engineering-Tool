import requests
import json
import os
import glob
import threading
import queue
from tkinter import messagebox

THREAD_LIMIT = 5


def clear_directory(dir_path):
    files = glob.glob(dir_path + "/*")
    for file in files:
        try:
            os.remove(file)
        except OSError as e:
            print(f"Error: {file} : {e.strerror}")


def clear_file(file_path):
    try:
        open(file_path, 'w').close()
    except OSError as e:
        print(f"Error: {file_path} : {e.strerror}")


def get_api_json(url, headers):
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 500:
        return {"error": 500}
    elif response.status_code == 401:
        raise requests.exceptions.HTTPError(f"Copy new cookie into login.txt: {response.status_code}")
    else:
        raise requests.exceptions.HTTPError(f"Failed to get data, status code: {response.status_code}")


def refill_blacklist(api_url, cookie):
    try:
        blacklist_file = 'blacklist.txt'
        clear_file(blacklist_file)
        blacklist_candidates = queue.Queue()

        headers = {
            "Cookie": f"DynamicsOwinAuth={cookie}"
        }

        response_json = get_api_json(api_url, headers)
        urls = extract_matching_urls(response_json, "")

        semaphore = threading.Semaphore(THREAD_LIMIT)

        threads = []
        for x in urls:
            t = threading.Thread(target=worker, args=(api_url, x, headers, blacklist_candidates, semaphore))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        with open(blacklist_file, 'w') as f:
            while not blacklist_candidates.empty():
                f.write(blacklist_candidates.get() + '\n')

        messagebox.showinfo("Success", "Data blacklist refilled.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def worker(api_url, x, headers, blacklist_candidates, semaphore):
    with semaphore:
        url = api_url + '/' + x + '?$top=1'
        print(url)
        response = get_api_json(url, headers)
        if 'error' in response or not response['value']:
            blacklist_candidates.put(x)


def extract_matching_urls(response_json, search_param):
    return [item['url'] for item in response_json['value'] if search_param in item['url']]


def get_data(api_url, cookie, entity_search_param, search_param_file):
    try:
        blacklist = set(line.strip() for line in open('blacklist.txt'))

        save_data_from_last_run(api_url, cookie, entity_search_param, search_param_file)
        headers = {
            "Cookie": f"DynamicsOwinAuth={cookie}"
        }

        response_json = get_api_json(api_url, headers)
        urls = extract_matching_urls(response_json, entity_search_param)

        urls = [url for url in urls if url not in blacklist]

        semaphore = threading.Semaphore(THREAD_LIMIT)

        threads = []
        for i, url in enumerate(urls):
            t = threading.Thread(target=save_json_to_file,
                                 args=(api_url, url, headers, search_param_file, i, semaphore))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        messagebox.showinfo("Success", "Data saved successfully.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def save_json_to_file(api_url, url, headers, search_parm_inside_file, i, semaphore):
    with semaphore:
        entity = url
        url = api_url + "/" + url
        try:
            json_data = get_api_json(url, headers)
            json_string = json.dumps(json_data, indent=4)

            if search_parm_inside_file in json_string:
                with open("result/" + "MATCH_" + f"data{i}_{entity}.txt", "w") as file:
                    file.write(json_string)

            print(f"Data saved successfully to data{i}_{entity}.txt.")
        except requests.exceptions.HTTPError as e:
            print(f"Error calling API: {e}")


def load_data_from_last_run(filename):
    try:
        with open(filename, "r") as f:
            if os.stat(filename).st_size == 0:
                save_data_from_last_run("", "", "", "")
            else:
                data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"{filename} not found.")
        return None


def save_data_from_last_run(api_url, cookie, entity_search_param, search_param_file):
    data = {
        'api_url': api_url,
        'cookie': cookie,
        'entity_search_param': entity_search_param,
        'search_param_file': search_param_file
    }

    with open('last_run_data.json', 'w') as f:
        json.dump(data, f)
