
# coding:utf-8

import asyncio
import os
import re
import time
from os import DirEntry
from typing import Dict, List
import sys
import aiohttp
import spotify
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, ID3NoHeaderError, error
from mutagen.mp3 import MP3, HeaderNotFoundError

start = time.time()

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", None)
SPOTIFY_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", None)
if SPOTIFY_SECRET is None:
    raise RuntimeError("Environment variables not set")
FILE_PATH = os.environ.get("FILE_PATH",
                           "C:\\Users\\ximon\\Downloads\\Music\\Starred")
# Get all files from music folder
with os.scandir(FILE_PATH) as music_files:
    music_files: List[DirEntry] = (
     {entry for entry in music_files if entry.name.endswith('mp3')})

song_expressions = ['..', 'mp3', 'webm', 'lyric', 'video', 'official', 'audio',
                    'from suicide squad', 'album', 'ft', '.'
                    'version']
song = re.compile(r'\b(?:%s)\b' % '|'.join(song_expressions))


def cleanup_name(i) -> str:
    return re.sub(song, "", re.sub(r"(【|_|{|\(|\[)(.*?)(]|\)|}|_|】)", "", i))


song_results: Dict[str, str] = {}
art_gather = []


async def main():
    print(f"Preparing to work on {len(music_files)} songs...")
    client = spotify.Client(SPOTIFY_CLIENT_ID, SPOTIFY_SECRET)
    song: DirEntry
    entry: spotify.SearchResults
    tracks: Dict[DirEntry, spotify.SearchResults]
    tasks = []
    for song in music_files:
        tasks.append(asyncio.create_task(client.search(
            cleanup_name(song.name) if cleanup_name(song.name) != "" or
            None else "Song not available",  # Fixes bad request issue
            types=["track"])))
    try:
        done = await asyncio.gather(*tasks)
    except (spotify.SpotifyException, TypeError):
        print("script has been ratelimited, waiting and "
              "running the script again, please do not close.")
        await asyncio.sleep(100)
        os.execl(sys.executable, sys.executable, *sys.argv)
    track: spotify.Track
    songs = dict(zip(music_files, done))

    async def cover_download(url: str, song: DirEntry) -> None:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                raw_data = await r.read()
        tracks: spotify.SearchResults
        try:
            cover_art = MP3(song.path, ID3=ID3)
        except HeaderNotFoundError:
            pass
        try:
            cover_art.add_tags()
        except error:
            pass
        cover_art.tags.add(APIC(
            mime="image/jpeg", desc=u"Cover",
            data=raw_data))
        cover_art.save()

    sem = asyncio.Semaphore(3)

    for song, tracks in songs.items():
        if tracks[0] is not None:
            art_gather.append(cover_download(tracks[0].albums[0].url,
                                             song=song))

    async with sem:
        await asyncio.gather(*art_gather)

    songs_not_found = 0
    for song, tracks in songs.items():
        tracks: spotify.SearchResults
        try:
            track = tracks.tracks[0]
        except Exception:
            songs_not_found += 1
            continue
        try:
            mutagen = EasyID3(song.path)
        except ID3NoHeaderError:
            continue
        mutagen['title'] = track.name
        mutagen['album'] = track.album.name
        mutagen['artist'] = track.artist.name
        mutagen['genre'] = ""
        mutagen.save()
        song_results[song.name] = track.name
    if songs_not_found != 0:
        print(f"{songs_not_found} songs not found in spotify's api")
    await client.close()
    cleanup_file_names()


def c_n(name: str) -> str:  # Clean name to avoid illegal characters
    return name.replace("?", "︖").replace(
     "*", "∗").replace("!", "!").replace("/",
                                         "")


def cleanup_file_names() -> None:
    print("Cleaning up file names...")
    cleanup = os.listdir(FILE_PATH)
    print(f"Renaming {len(cleanup)} songs...")
    for item in cleanup:
        if item.endswith(".mp3"):
            try:
                os.rename(f"{FILE_PATH}\\{item}",
                          f"{FILE_PATH}\\{song_results[item]}.mp3")
            except KeyError:
                try:
                    os.rename(f"{FILE_PATH}\\{item}",
                              f"{FILE_PATH}\\{cleanup_name(item)}.mp3")
                except FileExistsError:
                    try:
                        os.remove(f"{FILE_PATH}\\{song_results[item]}.mp3")
                        os.remove(f"{FILE_PATH}\\{cleanup_name(item)}.mp3")
                    except Exception:
                        pass
            except FileExistsError:
                try:
                    os.remove(f"{FILE_PATH}\\{song_results[item]}.mp3")
                    os.remove(f"{FILE_PATH}\\{cleanup_name(item)}.mp3")
                except Exception:
                    pass
            except FileNotFoundError:
                continue
            except OSError:
                try:
                    os.rename(f"{FILE_PATH}\\{item}",
                              f"{FILE_PATH}\\{c_n(song_results[item])}.mp3")
                except FileExistsError:
                    try:
                        os.remove(f"{FILE_PATH}\\{song_results[item]}.mp3")
                        os.remove(f"{FILE_PATH}\\{cleanup_name(item)}.mp3")
                    except Exception:
                        pass

    print(f"Operation took {time.time() - start:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
