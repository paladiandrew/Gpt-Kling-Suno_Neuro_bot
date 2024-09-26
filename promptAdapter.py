import aiohttp
import asyncio
import re
from models import create_test_video, create_video, create_audio, concatenate


API_KEY = "AQVN29iNFWLm5DnsJDlmY6yGZNmPHV8QX_XEYjFA"
FOLDER_ID = "b1gv5il4qe6vdpf2c8na"
MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt-lite"


def clean_text(text, flag):
    # Удаляем слова 'prompt' и 'description' независимо от регистра
    text = re.sub(
        r"\b(prompt|description|properties|incorrect elements)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Удаляем все символы, кроме букв, запятых и точек
    text = re.sub(r"[^a-zA-Z,. ]", " ", text)

    # Заменяем точки на точки с пробелом за ними в конце
    text = re.sub(r"\.(?! )", ". ", text)

    # Убираем переходы на новую строку и лишние пробелы
    text = text.replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)

    # Если флаг установлен, заменяем точки на запятые и приводим текст к нижнему регистру
    if flag:
        text = text.replace(".", ",").lower()
        # Удаляем последнюю запятую, если она есть
        if text.endswith(","):
            text = text[:-1]

    return text


async def generate_prompts(req_api, count):
    prompts = []

    translation_prompt = (
        "Create a clear and specific prompt for generating a video based on the following text. "
        "Please follow these guidelines, all conditions are mandatory:\n"
        "1. Describe the scene in a simple and direct way.\n"
        "2. Focus on a single action or movement within the scene, ensuring actions are very slow and smooth.\n"
        "3. Avoid idioms, complex phrases, and negative descriptions.\n"
        "4. Include relevant visual details to enrich the description.\n"
        "5. Make sure the scene and objects do not change, and no new elements are introduced.\n"
        "6. Keep the description concise and limit the number of actions.\n"
        "7. Introduce as few actions as possible for clarity, ensuring they flow smoothly.\n"
        "Base the prompt on this text:\n"
        f"{req_api.textPrompt}\n"
        "Make sure the prompt is in English and follows these instructions carefully."
    )

    english_prompt = await get_yandex_gpt_response(
        translation_prompt, API_KEY, FOLDER_ID
    )
    last_prompt = clean_text(english_prompt, False)

    prompts.append(last_prompt)
    for i in range(count):
        continuation_prompt = (
            "Generate a video prompt that continues smoothly from the following scene:\n"
            f"{last_prompt}\n"
            "Adhere to these guidelines strictly, all conditions are mandatory:\n"
            "1. Describe the scene clearly and specifically, ensuring it flows naturally and smoothly from the previous description.\n"
            "2. Focus on movement and actions, maintaining continuity with the prior scene, and ensuring actions are very slow and smooth.\n"
            "3. Avoid idioms, complex phrases, and negative language.\n"
            "4. Include relevant visual details to enhance the description if needed, without changing the scene or adding new objects.\n"
            "5. Keep the prompt concise, avoiding multiple actions or scenes in one prompt.\n"
            "6. Introduce as few new actions as possible for simplicity, and ensure they are slow and smooth.\n"
            "7. Do not add new events or objects not present in the scene, and keep the background and existing elements unchanged.\n"
            "Ensure the prompt is written in English and follows these instructions precisely."
        )

        new_prompt = await get_yandex_gpt_response(
            continuation_prompt, API_KEY, FOLDER_ID
        )
        cleaned_new_prompt = clean_text(new_prompt, False)
        prompts.append(cleaned_new_prompt)
        last_prompt = last_prompt + ". " + cleaned_new_prompt

    new_user_prompt = ""
    for i in range(len(prompts)):
        new_user_prompt = new_user_prompt + prompts[i]

    cleaned_negative_prompt = await generate_negative_prompt(prompts[0])
    cleaned_music_prompt = await generate_suno_prompt(new_user_prompt)

    print("--------------------------------")
    print(last_prompt)
    print("--------------------------------")
    print(cleaned_music_prompt)
    print("--------------------------------")
    print(cleaned_negative_prompt)
    print("--------------------------------")

    req_api.videoPrompt = prompts
    req_api.audioPrompt = cleaned_music_prompt
    req_api.negative_prompt = cleaned_negative_prompt
    return req_api


async def generate_negative_prompt(prompt):
    negative_prompt = f"""
        Please follow these guidelines (all conditions are mandatory):\n
        1. Analyze the description:\n
        {prompt}\n
        2. For this description, list properties, elements, actions, and states **that cannot appear in the description's context**.\n
        3. Use 1-3 word phrases, separated by commas.\n
        4. **Avoid unnecessary words, explanations, conjunctions, and negations.**\n
        5. Do not use words from the description.\n
        6. Answer on English.
    """

    negative_prompt_text = await get_yandex_gpt_response(
        negative_prompt, API_KEY, FOLDER_ID
    )
    cleaned_negative_prompt = clean_text(negative_prompt_text, True)
    return cleaned_negative_prompt


async def generate_suno_prompt(prompt):
    suno_prompt = (
        "Based on the following description, create a prompt for background music that perfectly fits the described scene. Provide only the prompt text, in English, without additional explanations. Focus solely on describing the type of music that aligns with the scene described in the text:"
        f"{prompt}"
    )
    music_prompt = await get_yandex_gpt_response(suno_prompt, API_KEY, FOLDER_ID)
    cleaned_music_prompt = clean_text(music_prompt, False)
    return cleaned_music_prompt


async def create_yandex_gpt_operation(prompt, api_key, folder_id):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completionAsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {api_key}",
        "x-folder-id": folder_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=prompt) as response:
            if response.status == 200:
                data = await response.json()
                return data["id"]
            else:
                return None


async def check_yandex_gpt_operation_status(operation_id, api_key):
    url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"
    headers = {"Authorization": f"Api-Key {api_key}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"statusCode": response.status}


async def get_yandex_gpt_response(prompt_text, api_key, folder_id):
    prompt = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.5,
            "maxTokens": "20000",
        },
        "messages": [
            {"role": "user", "text": prompt_text},
        ],
    }

    operation_id = await create_yandex_gpt_operation(prompt, api_key, folder_id)
    if not operation_id:
        return "Ошибка создания операции"

    while True:
        result = await check_yandex_gpt_operation_status(operation_id, api_key)

        if isinstance(result, dict):
            status_code = result.get("done")
            if status_code == True:
                if "response" in result:
                    response = result["response"]
                    if "alternatives" in response and response["alternatives"]:
                        alternative = response["alternatives"][0]
                        if (
                            "message" in alternative
                            and "text" in alternative["message"]
                        ):
                            message = alternative["message"]
                            return message["text"].strip()
                        else:
                            return "Сообщение не найдено в альтернативе"
                    else:
                        return "Альтернативы не найдены в ответе"
                else:
                    return "Ответ не содержит ключ 'response'"
            elif status_code and status_code >= 400:

                return f"Ошибка операции: {result.get('error', 'Неизвестная ошибка')}"
        else:

            return "Ошибка при проверке статуса операции"

        await asyncio.sleep(10)


async def process_requests(req_api, update, sec):
    # Промпт для перевода и расширения
    if update and sec == "30":
        video_path = await create_video(req_api, 5)
        if req_api.has_audio:
            result = await concatenate(req_api)
            final_video_path, updated_req = result
            req_api = updated_req
            return final_video_path, req_api
        else:
            return video_path, req_api
    elif sec == "30":
        req_api = await generate_prompts(req_api, 5)
        video_path = await create_test_video(req_api)
        # Создание аудио
        if req_api.has_audio:
            await create_audio(req_api)

            # Конкатенация видео и аудио
            result = await concatenate(req_api)
            final_video_path, updated_req = result
            req_api = updated_req
            return final_video_path, req_api
        else:
            return video_path, req_api
    elif sec == "20":
        req_api = await generate_prompts(req_api, 6)
        await create_test_video(req_api)
        video_path = await create_video(req_api, 3)
        if req_api.has_audio:
            await create_audio(req_api)
            result = await concatenate(req_api)
            final_video_path, updated_req = result
            req_api = updated_req
            return final_video_path, req_api
        else:
            return video_path, req_api
    elif sec == "10":
        req_api = await generate_prompts(req_api, 6)
        await create_test_video(req_api)
        video_path = await create_video(req_api, 1)
        if req_api.has_audio:
            await create_audio(req_api)
            result = await concatenate(req_api)
            final_video_path, updated_req = result
            req_api = updated_req
            return final_video_path, req_api
        else:
            return video_path, req_api
