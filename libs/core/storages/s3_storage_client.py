import os
import glob
import requests
import json
from core.storages import BaseStorageClient
from core.automan_client import AutomanClient


class S3StorageClient(BaseStorageClient):

    def __init__(self, storage_config, archive_config):
        super(S3StorageClient, self).__init__(storage_config)
        os.mkdir('/s3')
        self.rosbag_path = '/s3/rosbag.bag'
        self.output_path = archive_config['archive_dir']
        os.makedirs(self.output_path)
        self.target_url = storage_config['target_url']
        self.storage_id = storage_config['storage_id']

    def download(self, url=None):
        if url is None:
            url = self.target_url
        req = requests.get(url, stream=True)
        if 200 <= req.status_code < 300:
            with open(self.rosbag_path, 'wb') as f:
                f.write(req.content)
        else:
            print(f's3 download status_code = {req.status_code}. body = {req.text}')

    def upload(self, automan_info, upload_dir=None, ext=''):
        if upload_dir is None:
            upload_dir = self.output_path
        archive = glob.glob(self.output_path + '*' + ext)
        for filepath in archive:
            name = os.path.split(filepath)[1]
            data = {
                'storage_id': str(self.storage_id),
                'key': self.output_path + name}
            res = AutomanClient.send_result(
                    automan_info, data, automan_info['presigned']).text
            presigned = json.loads(res)
            headers = {'content-type': 'application/octet-stream'}
            res = requests.put(
                    presigned['url'],
                    headers=headers,
                    data=open(filepath, 'rb')
                    )
            if 200 > res.status_code >= 300:
                print(f's3 upload status_code = {res.status_code}. body = {res.text}')

    def list(self):
        pass

    def get_input_path(self):
        return self.rosbag_path

    def get_output_dir(self):
        return self.output_path
