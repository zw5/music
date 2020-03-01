
# coding:utf-8

import asyncio
import os
import tempfile
from os import DirEntry
from typing import List
import re

import aiohttp
import spotify
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, ID3NoHeaderError, error
from mutagen.mp3 import MP3, HeaderNotFoundError

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", None)
SPOTIFY_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", None)
if SPOTIFY_SECRET is None:
    raise RuntimeError("Environment variables not set")
FILE_PATH = os.environ.get("FILE_PATH",
                           "C:\\Users\\ximon\\Downloads\\Music\\Starred")
# Get all files from music folder
with os.scandir(FILE_PATH) as music_files:
    music_files: List[DirEntry] = (
        {
            entry for entry in music_files if entry.name.endswith('mp3')
        }
    )


def cleanup_name(item) -> str:
    return re.sub(r"(【|_|{|\(|\[)(.*?)(]|\)|}|_|】)", "", item).lower().replace(
        ".mp3", "").replace(
        "..mp3", "").replace(
        ".webm", "").replace(
        ".mp4", "").replace(
        "..", ".")


async def main():
    client = spotify.Client(SPOTIFY_CLIENT_ID, SPOTIFY_SECRET)
    song: DirEntry
    entry: spotify.SearchResults
    tasks = []
    for song in music_files:
        tasks.append(asyncio.create_task(client.search(
            cleanup_name(song.name) if cleanup_name(song.name) != "" or
            None else "Song not available", # Fixes bad request issue
            types=["track"])))
    done = await asyncio.gather(*tasks)
    track: spotify.Track
    songs = dict(zip(music_files, done))

    async def cover_download(url):
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                data = await r.read()
        f, path = tempfile.mkstemp(suffix=".jpg")
        f = open(path, "wb")
        f.write(data)
        return path

    for song, tracks in songs.items():
        tracks: spotify.SearchResults
        try:
            track = tracks.tracks[0]
        except Exception:
            print(f"Results not found for song {song.name}")
            continue
        try:
            cover_art = MP3(song.path, ID3=ID3)
        except HeaderNotFoundError:
            continue
        try:
            cover_art.add_tags()
        except error:
            pass
        p = await cover_download(track.album.images[0].url)
        with open(p, "rb") as f:
            raw_image = f.read()
        cover_art.tags.add(APIC(
            mime="image/jpeg", desc=u"Cover",
            data=raw_image))
        cover_art.save()

    for song, tracks in songs.items():
        tracks: spotify.SearchResults
        try:
            track = tracks.tracks[0]
        except Exception:
            print(f"Results not found for song {cleanup_name(song.name)}")
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
    await client.close()
    cleanup_file_names()


def cleanup_file_names():
    print("Cleaning up file names...")
    cleanup = os.listdir(FILE_PATH)
    for item in cleanup:
        if item.endswith(".mp3"):
            print(f"Renaming {item}, to {cleanup_name(item).strip()}")
            try:
                os.rename(f"{FILE_PATH}\\{item}",
                          f"{FILE_PATH}\\{cleanup_name(item).strip()}.mp3")
            except FileExistsError:
                continue


if __name__ == "__main__":
    asyncio.run(main())
