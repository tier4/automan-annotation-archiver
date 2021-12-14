#!/usr/bin/env python
import argparse
import json
import os
import sys
import re
import requests
import shutil
sys.path.append(os.path.join(os.path.dirname(__file__), '../libs'))
from core.storage_client_factory import StorageClientFactory
from core.automan_client import AutomanClient

TEMP_DIR = '/temp'

DATA_TYPE_PCD = 'PCD'
DATA_TYPE_IMAGE = 'IMAGE'

EXT_PCD = '.pcd'
EXT_IMAGE = '.jpg'


def get_cv_color(colors, name):
    color = colors[name]
    cv_color = (int(color[5:7], 16), int(color[3:5], 16), int(color[1:3], 16))
    return cv_color


class AutomanArchiver(object):

    @classmethod
    def archive(cls, automan_info, archive_info):
        print(archive_info)

        annotations_dir = os.path.join(TEMP_DIR, 'Annotations')
        images_dir = os.path.join(TEMP_DIR, 'Images')
        image_annotations_dir = os.path.join(TEMP_DIR, 'Images_Annotations')

        # whether or not to write image in bag file to image files
        is_including_image = archive_info.get('include_image', False)

        project_id = archive_info['project_id']
        annotation_id = archive_info['annotation_id']
        dataset_id = archive_info['dataset_id']

        max_frame = cls.__get_frame_range(
            automan_info, archive_info['project_id'], archive_info['annotation_id'])
        colors = cls.__get_annotation_color(automan_info, archive_info['project_id'])
        candidates = cls.__get_candidates(
            automan_info, archive_info['project_id'], archive_info['original_id'])

        # ensure directory
        os.makedirs(annotations_dir, exist_ok=True)

        if 'extractor_version' in archive_info:
            extractor_version = archive_info['extractor_version']
        else:
            extractor_version = [0, 0, 0]
        format_version = {
            'major': extractor_version[0],
            'minor': extractor_version[1],
            'patch': extractor_version[2],
        }
        for i in range(max_frame):
            frame_num = i + 1
            annotation = cls.__get_annotation(
                automan_info=automan_info,
                project_id=project_id,
                annotation_id=annotation_id,
                frame=frame_num,
            )
            annotation['format_version'] = format_version

            annotation_frame = None
            for candidate in candidates:
                if candidate['ext'] == EXT_PCD:
                    annotation_frame = cls.__get_annotation_frame(
                        automan_info=automan_info,
                        project_id=project_id,
                        dataset_id=dataset_id,
                        candidate_id=candidate['id'],
                        frame=frame_num,
                    )

            annotation['timestamp'] = {
                'secs': annotation_frame['frame']['secs'],
                'nsecs': annotation_frame['frame']['nsecs'],
            }

            with open(os.path.join(annotations_dir, str(frame_num).zfill(6) + '.json'), mode='w') as fp:
                fp.write(json.dumps(annotation))

            if is_including_image:
                for candidate in candidates:
                    file_name = cls.__get_annotation_image(
                        automan_info=automan_info,
                        project_id=project_id,
                        dataset_id=dataset_id,
                        candidate_id=candidate['id'],
                        frame=i + 1,
                        ext=candidate['ext'],
                        images_dir=images_dir,
                    )
                    if file_name is not None:
                        cls.__draw_annotation(file_name, annotation, colors, images_dir, image_annotations_dir)

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
            ext = EXT_IMAGE if record['data_type'] == 'IMAGE' else EXT_PCD
            candidates.append({'id': record['candidate_id'], 'ext': ext})
        return candidates

    @staticmethod
    def __get_annotation(automan_info, project_id, annotation_id, frame):
        path = '/projects/' + str(project_id) + '/annotations/' + str(annotation_id) \
            + '/frames/' + str(frame) + '/objects/'
        return AutomanClient.send_get(automan_info, path).json()

    @staticmethod
    def __get_annotation_image(automan_info, project_id, dataset_id, candidate_id, frame, ext, images_dir):
        img_url = AutomanArchiver.__get_annotation_frame(automan_info, project_id, dataset_id, candidate_id, frame)['image_link']
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

        # write images
        os.makedirs(images_dir, exist_ok=True)
        file_name = str(candidate_id) + '_' + str(frame).zfill(6) + ext
        img_path = os.path.join(images_dir, file_name)
        with open(img_path, mode='wb') as frame:
            frame.write(res.content)
        if ext == EXT_IMAGE:
            return file_name
        return None

    @staticmethod
    def __get_annotation_frame(automan_info, project_id, dataset_id, candidate_id, frame):
        path = '/projects/' + str(project_id) + '/datasets/' + str(dataset_id) \
               + '/candidates/' + str(candidate_id) + '/frames/' + str(frame) + '/'
        return AutomanClient.send_get(automan_info, path).json()

    @staticmethod
    def __draw_annotation(file_name, annotation, colors, images_dir, image_annotations_dir):
        import cv2

        if annotation['count'] == 0:
            return 0

        os.makedirs(image_annotations_dir, exist_ok=True)
        img = cv2.imread(os.path.join(images_dir, file_name))
        for a in annotation['records']:
            for c in a['content']:
                if 'min_x_2d' not in a['content'][c]:
                    continue
                bbox = ((a['content'][c]['min_x_2d'], a['content'][c]['min_y_2d']),
                        (a['content'][c]['max_x_2d'], a['content'][c]['max_y_2d']))
                cv_color = get_cv_color(colors, a['name'])
                cv2.rectangle(img, bbox[0], bbox[1], cv_color, 2)
        cv2.imwrite(os.path.join(image_annotations_dir, file_name), img)

    @staticmethod
    def __get_annotation_color(automan_info, project_id):
        path = '/projects/' + str(project_id) + '/'
        res = AutomanClient.send_get(automan_info, path).json()
        colors = {}
        for record in res['klassset']['records']:
            config = json.loads(record['config'])
            colors[record['name']] = config['color']
        return colors


def main(automan_info, archive_info, storage_type, storage_info):
    automan_info = json.loads(automan_info)
    archive_info = json.loads(archive_info)

    archive_dir = archive_info['archive_dir'].rstrip('/') + '/'

    storage_client = StorageClientFactory.create(
        storage_type,
        json.loads(storage_info),
        archive_info
    )

    AutomanArchiver.archive(automan_info, archive_info)
    shutil.make_archive(
        archive_dir + archive_info['archive_name'],
        'gztar',
        root_dir=TEMP_DIR)
    if storage_type == 'AWS_S3':
        storage_client.upload(automan_info, archive_dir)

    # TODO post : ArchiviedLabelDataset
    data = {
        'file_path': archive_info['archive_dir'],
        'file_name': archive_info['archive_name'] + '.tar.gz',
        'annotation_id': archive_info['annotation_id'],
    }
    AutomanClient.send_result(automan_info, data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--storage_type', required=False)
    parser.add_argument('--storage_info', required=False)
    parser.add_argument('--automan_info', required=True)
    parser.add_argument('--archive_info', required=True)
    args = parser.parse_args()
    main(args.automan_info, args.archive_info, args.storage_type, args.storage_info)
