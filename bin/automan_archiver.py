#!/usr/bin/env python
import argparse
import json
import os
import sys
import re
import requests
import shutil
import cv2
sys.path.append(os.path.join(os.path.dirname(__file__), '../libs'))
from core.storage_client_factory import StorageClientFactory
from core.automan_client import AutomanClient

TEMP_DIR = '/temp'


def get_cv_color(colors, name):
    color = colors[name]
    cv_color = (int(color[5:7], 16), int(color[3:5], 16), int(color[1:3], 16))
    return cv_color


class AutomanArchiver(object):

    @classmethod
    def archive(cls, automan_info, archive_info):
        os.makedirs(TEMP_DIR + '/Annotations')
        os.makedirs(TEMP_DIR + '/Images')
        os.makedirs(TEMP_DIR + '/Images_Annotations')
        max_frame = cls.__get_frame_range(
            automan_info, archive_info['project_id'], archive_info['annotation_id'])
        colors = cls.__get_annotation_color(automan_info, archive_info['project_id'])
        candidates = cls.__get_candidates(
            automan_info, archive_info['project_id'], archive_info['original_id'])
        for i in range(max_frame):
            annotation = cls.__get_annotation(
                automan_info, archive_info['project_id'], archive_info['annotation_id'], i + 1)
            for candidate in candidates:
                file_name = cls.__get_annotation_image(
                    automan_info, archive_info['project_id'],
                    archive_info['dataset_id'], candidate['id'], i + 1, candidate['ext'])
                if file_name is not None:
                    cls.__draw_annotation(file_name, annotation, colors)

    @staticmethod
    def __get_frame_range(automan_info, project_id, annotation_id):
        path = '/projects/' + str(project_id) + '/annotations/' + str(annotation_id) + '/'
        res = AutomanClient.send_get(automan_info, path).json()
        dataset_path = '/projects/' + str(project_id) + '/datasets/' + str(res['dataset_id']) + '/'
        dataset = AutomanClient.send_get(automan_info, dataset_path).json()
        return dataset['frame_count']

    @staticmethod
    def __get_candidates(automan_info, project_id, original_id):
        path = '/projects/' + str(project_id) + '/originals/' + str(original_id) + '/candidates/'
        res = AutomanClient.send_get(automan_info, path).json()
        candidates = []
        for record in res['records']:
            ext = '.jpg' if record['data_type'] == 'IMAGE' else '.pcd'
            candidates.append({'id': record['candidate_id'], 'ext': ext})
        return candidates

    @staticmethod
    def __get_annotation(automan_info, project_id, annotation_id, frame):
        path = '/projects/' + str(project_id) + '/annotations/' + str(annotation_id) \
            + '/frames/' + str(frame) + '/objects/'
        res = AutomanClient.send_get(automan_info, path).json()
        # TODO format to "kitti format"
        with open(TEMP_DIR + '/Annotations/' + str(frame).zfill(6) + '.json', mode='w') as frame:
            frame.write(json.dumps(res))
        return res

    @staticmethod
    def __get_annotation_image(automan_info, project_id, dataset_id, candidate_id, frame, ext):
        path = '/projects/' + str(project_id) + '/datasets/' + str(dataset_id) \
            + '/candidates/' + str(candidate_id) + '/frames/' + str(frame) + '/'
        img_url = AutomanClient.send_get(automan_info, path).text
        if re.search(automan_info['host'], img_url):
            headers = {
                'Authorization': 'JWT ' + automan_info['jwt'],
            }
        else:
            headers = {}
        res = requests.get(img_url, headers=headers)
        if 200 > res.status_code >= 300:
            print(f'get annotation image status_code = {res.status_code}. body = {res.text}')
            return None
        file_name = str(candidate_id) + '_' + str(frame).zfill(6) + ext
        img_path = TEMP_DIR + '/Images/' + file_name
        with open(img_path, mode='wb') as frame:
            frame.write(res.content)
        if ext == '.jpg':
            return file_name
        return None

    @staticmethod
    def __draw_annotation(file_name, annotation, colors):
        if annotation['count'] == 0:
            return 0
        img = cv2.imread(TEMP_DIR + '/Images/' + file_name)
        for a in annotation['records']:
            for c in a['content']:
                if 'min_x_2d' not in a['content'][c]:
                    continue
                bbox = ((a['content'][c]['min_x_2d'], a['content'][c]['min_y_2d']),
                        (a['content'][c]['max_x_2d'], a['content'][c]['max_y_2d']))
                cv_color = get_cv_color(colors, a['name'])
                cv2.rectangle(img, bbox[0], bbox[1], cv_color, 2)
        cv2.imwrite(TEMP_DIR + '/Images_Annotations/' + file_name, img)

    @staticmethod
    def __get_annotation_color(automan_info, project_id):
        path = '/projects/' + str(project_id) + '/'
        res = AutomanClient.send_get(automan_info, path).json()
        colors = {}
        for record in res['klassset']['records']:
            config = json.loads(record['config'])
            colors[record['name']] = config['color']
        return colors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--storage_type', required=False)
    parser.add_argument('--storage_info', required=False)
    parser.add_argument('--automan_info', required=True)
    parser.add_argument('--archive_info', required=True)
    args = parser.parse_args()
    automan_info = json.loads(args.automan_info)
    archive_info = json.loads(args.archive_info)
    archive_dir = archive_info['archive_dir'].rstrip('/') + '/'

    storage_client = StorageClientFactory.create(
        args.storage_type,
        json.loads(args.storage_info),
        archive_info
    )

    AutomanArchiver.archive(automan_info, archive_info)
    shutil.make_archive(
        archive_dir + archive_info['archive_name'],
        'gztar',
        root_dir=TEMP_DIR)
    if args.storage_type == 'AWS_S3':
        storage_client.upload(automan_info, archive_dir)

    # TODO post : ArchiviedLabelDataset
    data = {
        'file_path': archive_info['archive_dir'],
        'file_name': archive_info['archive_name'] + '.tar.gz',
        'annotation_id': archive_info['annotation_id'],
    }
    AutomanClient.send_result(automan_info, data)
