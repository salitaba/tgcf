import datetime
import io
from typing import Union
from minio import Minio
from minio.error import S3Error
import os
import logging
from PIL import Image


class MinioUploader:
    def __init__(self, filename):
        self.minio_client = Minio(
            endpoint=os.getenv("MINIO_URL"),
            access_key=os.getenv("MINIO_ACCESS_KEY"),
            secret_key=os.getenv("MINIO_SECRET_KEY"),
        )
        self.bucket_name = "media"
        self.file_path = os.path.join('telegram_media', 'channels_media')
        self.filename = filename

    def upload_to_minio(self, have_thumbnail) -> bool:
        current_datetime = datetime.datetime.now()
        logging.info(f"upload_start_datetime {current_datetime}")
        result = None
        file_names = self.get_file_names(have_thumbnail)
        for file_name in file_names:
            try:
                result = self.minio_client.fput_object(bucket_name=self.bucket_name,
                                                       object_name=self.file_path + f"/{file_name}",
                                                       file_path=f"{file_name}")
                logging.info(f"Image {self.filename} uploaded to Minio CDN.")
            except Exception as e:
                try:
                    self.minio_client = Minio(
                        endpoint=os.getenv("MINIO_URL2"),
                        access_key=os.getenv("MINIO_ACCESS_KEY"),
                        secret_key=os.getenv("MINIO_SECRET_KEY"))
                    result = self.minio_client.fput_object(bucket_name=self.bucket_name,
                                                           object_name=self.file_path + f"/{file_name}",
                                                           file_path=f"{file_name}")
                    logging.info(f"Image {self.filename} uploaded to Minio CDN.")
                except Exception as e:
                    logging.info(f"{e}")

        for files in file_names:
            if os.path.exists(f"{files}"):
                os.remove(f"{files}")

        return result if result else False

    def get_file_names(self, have_thumbnail):
        non_extension_name, ext = os.path.splitext(self.filename)
        names = [f"{non_extension_name}.jpg"]
        if have_thumbnail:
            pictures_name = self.save_photo_thumbnail(self.filename)
            if pictures_name:
                names.append(pictures_name[0])

        return names

    @staticmethod
    def save_photo_thumbnail(photo):
        pictures_name = []
        size_285 = 285, 285
        try:
            file, ext = os.path.splitext(photo)
            im = Image.open(photo)
            im.thumbnail(size_285, Image.Resampling.LANCZOS)
            thumb_file = file + ".thumb_411"
            im.save(thumb_file, "JPEG")
            pictures_name.append(thumb_file)
        except Exception as Error:
            logging.info(Error)

        return pictures_name
