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
        if req.status_code == 200:
            with open(self.rosbag_path, 'wb') as f:
                f.write(req.content)
        else:
            print('status_code = ' + str(req.status_code))

    def upload(self, automan_info, upload_dir=None, ext=''):
        if upload_dir is None:
            upload_dir = self.output_path
        archive = glob.glob(self.output_path + '*' + ext)
        for file in archive:
            name = os.path.split(file)[1]
            params = {
                'storage_id': str(self.storage_id),
                'key': self.output_path + name}
            res = AutomanClient.send_get(
                automan_info, automan_info['presigned'], params).text
            presigned = json.loads(res)
            with open(file, 'rb') as f:
                res = requests.post(
                    presigned['url'],
                    data=presigned['fields'],
                    files={'file': (file, f)})
                if res.status_code != 204:
                    print('status_code = ' + str(res.status_code) + ': ' + res.text)

    def list(self):
        pass

    def get_input_path(self):
        return self.rosbag_path

    def get_output_dir(self):
        return self.output_path
