"""
Radio Downloader - Scarica chunk audio dalle radio con headers corretti
Risolve problemi di 403/502 usando Python urllib con headers browser
"""

import os
import urllib.request
import subprocess
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

RADIO_CACHE_DIR = "/tmp/xiaozhi_radio"


def download_radio_chunk(url: str, output_path: str, duration: int = 60, referer: str = None) -> bool:
    """
    Scarica un chunk di radio usando Python urllib (più affidabile di ffmpeg per headers)
    poi converte in MP3 con ffmpeg

    Args:
        url: URL dello stream
        output_path: percorso file output (.mp3)
        duration: durata in secondi
        referer: URL referer per CDN
    """
    try:
        os.makedirs(RADIO_CACHE_DIR, exist_ok=True)

        # Headers browser completi
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'audio',
            'Sec-Fetch-Mode': 'no-cors',
        }

        if referer:
            headers['Referer'] = referer
            headers['Origin'] = referer.rstrip('/')

        req = urllib.request.Request(url, headers=headers)

        # Per stream HLS (m3u8), usiamo ffmpeg con headers file
        if '.m3u8' in url or 'hls' in url.lower():
            return download_hls_stream(url, output_path, duration, headers)

        # Per stream MP3 diretti, scarica con Python
        raw_file = output_path.replace('.mp3', '_raw.mp3')

        try:
            # Calcola bytes da scaricare (approssimativo: 128kbps = 16KB/s)
            bytes_to_download = duration * 16 * 1024

            with urllib.request.urlopen(req, timeout=duration + 30) as resp:
                if resp.status != 200:
                    logger.bind(tag=TAG).error(f"HTTP {resp.status} per {url}")
                    return False

                with open(raw_file, 'wb') as f:
                    downloaded = 0
                    while downloaded < bytes_to_download:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                logger.bind(tag=TAG).info(f"Scaricati {downloaded} bytes da {url}")

            # Converti/normalizza con ffmpeg
            if os.path.exists(raw_file) and os.path.getsize(raw_file) > 1000:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", raw_file,
                    "-t", str(duration),
                    "-c:a", "libmp3lame",
                    "-b:a", "128k",
                    output_path
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=60)

                # Cleanup
                if os.path.exists(raw_file):
                    os.remove(raw_file)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    logger.bind(tag=TAG).info(f"Radio salvata: {output_path}")
                    return True

        except urllib.error.HTTPError as e:
            logger.bind(tag=TAG).error(f"HTTP Error {e.code}: {e.reason} - {url}")
            return False
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore download: {e}")
            return False

        return False

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore generale download radio: {e}")
        return False


def download_hls_stream(url: str, output_path: str, duration: int, headers: dict) -> bool:
    """
    Scarica stream HLS usando ffmpeg con headers file

    Args:
        url: URL HLS (.m3u8)
        output_path: percorso file output
        duration: durata in secondi
        headers: dict con headers HTTP
    """
    try:
        # Crea file temporaneo con headers
        headers_file = "/tmp/ffmpeg_headers.txt"
        with open(headers_file, 'w') as f:
            for key, value in headers.items():
                f.write(f"{key}: {value}\r\n")

        # Leggi headers come stringa
        with open(headers_file, 'r') as f:
            headers_str = f.read()

        cmd = [
            "ffmpeg", "-y",
            "-headers", headers_str,
            "-i", url,
            "-t", str(duration),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            output_path
        ]

        logger.bind(tag=TAG).debug(f"HLS download: {url[:50]}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=duration + 60
        )

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.bind(tag=TAG).info(f"HLS stream salvato: {output_path}")
            return True

        # Log errore
        if result.stderr:
            stderr = result.stderr.decode('utf-8', errors='ignore')[-300:]
            logger.bind(tag=TAG).error(f"FFmpeg HLS error: {stderr}")

        return False

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore HLS download: {e}")
        return False


# Test function
if __name__ == "__main__":
    # Test Rai Radio 1
    result = download_radio_chunk(
        "https://icestreaming.rai.it/1.mp3",
        "/tmp/test_rai.mp3",
        10,
        "https://www.raiplayradio.it/"
    )
    print(f"Test Rai Radio 1: {'OK' if result else 'FAIL'}")
