import aiohttp
import asyncio
import os
from aiofiles import open as aio_open
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips
from moviepy.audio.fx import audio_fadeout

DEFAULT_API_KEY = "d"


class reqApi:
    def __init__(self, tgId, prompt):
        self.tgId = tgId
        self.textPrompt = prompt
        self.videoPrompt = [prompt]
        self.audioPrompt = ""
        self.video_header = {"X-API-Key": DEFAULT_API_KEY}
        self.audio_header = {"X-API-Key": DEFAULT_API_KEY}
        self.video_task = ""
        self.audio_task = ""
        self.negative_prompt = ""
        self.duration = 0  # Добавлено: длительность ролика
        self.screen_format = "16:9"  # Добавлено: формат экрана
        self.has_audio = True  # Добавлено: наличие аудио


async def video_url_func(my_json: dict):
    if my_json is None:
        print("Error: Received None as my_json")
        return None

    # Проверяем наличие необходимых ключей
    data = my_json.get("data")
    if not data:
        print("Error: 'data' key is missing in the JSON")
        return None

    works = data.get("works", [])
    if not works:
        print("Error: 'works' key is missing or empty in the 'data' dictionary")
        return None

    resource = works[0].get("resource", {})
    if not resource:
        print("Error: 'resource' key is missing in the first item of 'works'")
        return None

    video_url = resource.get("resourceWithoutWatermark")
    if not video_url:
        print("Error: 'resourceWithoutWatermark' key is missing or empty in 'resource'")
        return None

    return video_url


async def create_test_video(user: reqApi) -> str:
    print(type(user.videoPrompt[0]))
    print(user.videoPrompt[0])
    print(user.video_header)
    print(user.audio_header)
    print("\n\n\n\n\n\n\n")
    JSON = {
        "negative_prompt": user.negative_prompt,
        "prompt": user.videoPrompt[0],
        "creativity": 0.6,
        "duration": 5,
        "aspect_ratio": user.screen_format,
        "professional_mode": True,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.piapi.ai/api/kling/v1/video",
            headers=user.video_header,
            json=JSON,
        ) as post_resp:
            post_json = await post_resp.json()
            await asyncio.sleep(10)
            task_id = post_json["data"]["task_id"]
            user.video_task = task_id
            print(task_id)
            video_url = ""
            while True:
                await asyncio.sleep(6)
                async with session.get(
                    f"https://api.piapi.ai/api/kling/v1/video/{task_id}",
                    headers=user.video_header,
                ) as get_resp:
                    get_json = await get_resp.json()
                    print(get_json)
                    video_url = await video_url_func(get_json)
                    if video_url is not None:
                        break
                print("Creating test video...")

            user_dir = f"./data/{user.tgId}"
            os.makedirs(user_dir, exist_ok=True)

            video_path = f"{user_dir}/reels.mp4"
            async with session.get(video_url) as video_resp:
                video_data = await video_resp.read()
                async with aio_open(video_path, "wb") as video_file:
                    await video_file.write(video_data)

            print("Test video created.")
            return video_path


async def extend_video(user: reqApi, number_of_extend: int):
    task_id = user.video_task
    print(task_id)
    JSON = {"prompt": user.videoPrompt[number_of_extend]}
    timeout = aiohttp.ClientTimeout(total=15 * 60)  # Установите таймаут 15 минут

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.post(
                f"https://api.piapi.ai/api/kling/v1/video/{task_id}/extend",
                json=JSON,
                headers=user.video_header,
            ) as post_resp:
                if post_resp.content_type == "application/json":
                    post_json = await post_resp.json()
                    task_id = post_json["data"]["task_id"]
                    print(task_id)
                    user.video_task = task_id
                else:
                    print(f"Unexpected response type: {post_resp}")
                    return

            while True:
                await asyncio.sleep(30)  # Увеличьте интервал ожидания
                try:
                    async with session.get(
                        f"https://api.piapi.ai/api/kling/v1/video/{task_id}",
                        headers=user.video_header,
                    ) as get_resp:
                        if get_resp.content_type == "application/json":
                            get_json = await get_resp.json()
                            print(get_json)
                            video_url = await video_url_func(get_json)
                            if video_url is not None:
                                return task_id
                        else:
                            print(f"Unexpected response type: {get_resp}")
                except asyncio.TimeoutError:
                    print("Request timed out. Retrying...")
                    continue
                print("Extending video...")
        except aiohttp.ClientError as e:
            print(f"An error occurred: {e}")


async def create_video(user: reqApi, new_reels_iteration_count) -> str:
    task_id = user.video_task
    user_dir = f"./data/{user.tgId}"
    for i_num in range(new_reels_iteration_count):
        await asyncio.sleep(2)
        task_id = await extend_video(user, i_num + 1)
        user.video_task = task_id

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.piapi.ai/api/kling/v1/video/{task_id}",
            headers=user.video_header,
        ) as get_resp:
            get_json = await get_resp.json()
            video_url = get_json["data"]["works"][0]["resource"][
                "resourceWithoutWatermark"
            ]
            async with session.get(video_url) as video_resp:
                video_data = await video_resp.read()
                video_path = f"{user_dir}/reels.mp4"
                async with aio_open(video_path, "wb") as video_file:
                    await video_file.write(video_data)
    return video_path


async def create_audio(user: reqApi):
    URL_to_generate = "https://api.piapi.ai/api/suno/v1/music"
    JSON = {
        "custom_mode": False,
        "mv": "chirp-v3-5",
        "input": {
            "prompt": user.audioPrompt,
            "title": "Without your love",
            "tags": "R&B",
            "continue_at": 0,
            "continue_clip_id": "",
        },
    }
    user_dir = f"./data/{user.tgId}"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            URL_to_generate, headers=user.audio_header, json=JSON
        ) as post_resp:
            post_json = await post_resp.json()
            print(post_json)
            task_id = post_json["data"]["task_id"]
            user.audio_task = task_id
            URL_to_get = f"https://api.piapi.ai/api/suno/v1/music/{task_id}"
            while True:
                await asyncio.sleep(10)
                async with session.get(
                    URL_to_get, headers=user.audio_header
                ) as get_resp:
                    get_json = await get_resp.json()
                    if get_json["data"]["status"] == "completed":
                        audio_url = get_json["data"]["clips"][
                            list(get_json["data"]["clips"].keys())[0]
                        ]["audio_url"]
                        async with session.get(audio_url) as audio_resp:
                            audio_data = await audio_resp.read()
                            async with aio_open(
                                f"{user_dir}/music.mp3", "wb"
                            ) as audio_file:
                                await audio_file.write(audio_data)
                        break
            print("Audio created.")


async def concatenate(user: reqApi) -> str:
    video_path = f"./data/{user.tgId}/reels.mp4"
    audio_path = f"./data/{user.tgId}/music.mp3"
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)

    # Ensure audio is not longer than the video
    if audio_clip.duration > video_clip.duration:
        audio_clip = audio_clip.subclip(0, video_clip.duration)

    # Set fade-out duration
    fade_out_duration = 1  # seconds

    # Apply fade-out to the audio
    audio_end = audio_clip.subclip(
        max(0, audio_clip.duration - fade_out_duration), audio_clip.duration
    )
    faded_audio_end = audio_end.audio_fadeout(fade_out_duration)

    # Create a new audio clip with fade-out effect
    if audio_clip.duration > fade_out_duration:
        main_audio = audio_clip.subclip(0, audio_clip.duration - fade_out_duration)
        final_audio = concatenate_audioclips([main_audio, faded_audio_end])
    else:
        final_audio = faded_audio_end

    # Set the audio to the video
    video_with_audio = video_clip.set_audio(final_audio)
    final_path = f"./data/{user.tgId}/final_reels.mp4"
    video_with_audio.write_videofile(final_path, codec="libx264", audio_codec="aac")
    return final_path, user
