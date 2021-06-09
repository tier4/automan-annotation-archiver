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

EXPORT_KLASS = [
    {
        'name': 'obstacle',
        'file_name': 'obstacles.json',
    },
    {
        'name': 'detection',
        'file_name': 'detections.json',
    },
]

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
        export_dir = os.path.join(TEMP_DIR, 'Exports')
        export_data = {}
        for k in EXPORT_KLASS:
            export_data[k['name']] = []

        # whether or not to write image in bag file to image files
        is_including_image = archive_info.get('include_image', False)

        max_frame = cls.__get_frame_range(
            automan_info, archive_info['project_id'], archive_info['annotation_id'])
        colors = cls.__get_annotation_color(automan_info, archive_info['project_id'])
        candidates = cls.__get_candidates(
            automan_info, archive_info['project_id'], archive_info['original_id'])
        map_to_base_link = cls.__get_map_to_base_link(
            automan_info, archive_info['project_id'], archive_info['dataset_id'])
        for i in range(max_frame):
            annotation = cls.__get_annotation(
                automan_info, archive_info['project_id'], archive_info['annotation_id'], i + 1,
                annotations_dir, map_to_base_link)
            if len(annotation['records']) > 0:
                cls.__add_export_data(annotation, map_to_base_link, i + 1, export_data)
            if is_including_image:
                for candidate in candidates:
                    file_name = cls.__get_annotation_image(
                        automan_info, archive_info['project_id'],
                        archive_info['dataset_id'], candidate['id'], i + 1, candidate['ext'], images_dir)
                    if file_name is not None:
                        cls.__draw_annotation(file_name, annotation, colors, images_dir, image_annotations_dir)
        cls.__save_export_data(export_data, export_dir)

    @staticmethod
    def __save_export_data(export_data, export_dir):
        os.makedirs(export_dir, exist_ok=True)
        for k in EXPORT_KLASS:
            with open(os.path.join(export_dir, k['file_name']), mode='w') as f:
                annotations = export_data[k['name']]
                if len(annotations) == 0:
                    annotations.append({
                        'annotation_frame_no': 1,
                        'map_to_base_link': None,
                        'records': [{
                            'name': k['name'],
                            'object_id': None,
                            'instance_id': '',
                            'content': {
                                'memo': '{"start_time": 0, "end_time": 0}',
                            }
                        }]
                    })
                f.write(json.dumps({'annotations': annotations}))


    @staticmethod
    def __add_export_data(annotation, map_to_base_link, frame, export_data):
        records = {}
        for k in EXPORT_KLASS:
            records[k['name']] = []
        for label in annotation['records']:
            name = label['name']
            if name in export_data:
                records[name].append(label)
        for k in EXPORT_KLASS:
            name = k['name']
            if len(records[name]) > 0:
                obj = {
                    'annotation_frame_no': frame,
                    'records': records[name]
                }
                if map_to_base_link is not None:
                    obj['map_to_base_link'] = map_to_base_link[frame - 1]
                export_data[name].append(obj)

    @staticmethod
    def __get_map_to_base_link(automan_info, project_id, dataset_id):
        path = '/projects/' + str(project_id) + '/datasets/' + str(dataset_id) \
            + '/map_to_base_link/'
        try:
            res = AutomanClient.send_get(automan_info, path).json()
        except json.JSONDecodeError:
            return None

        file_url = res['file_link']
        if re.search(automan_info['host'], file_url):
            headers = {
                'Authorization': 'JWT ' + automan_info['jwt'],
            }
        else:
            headers = {}
        res = requests.get(file_url, headers=headers)
        if 200 > res.status_code >= 300:
            return None

        try:
            return res.json()
        except json.JSONDecodeError:
            return None

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
    def __get_annotation(automan_info, project_id, annotation_id, frame, annotations_dir, map_to_base_link):
        path = '/projects/' + str(project_id) + '/annotations/' + str(annotation_id) \
            + '/frames/' + str(frame) + '/objects/'
        res = AutomanClient.send_get(automan_info, path).json()
        # TODO format to "kitti format"

        # ensure directory
        os.makedirs(annotations_dir, exist_ok=True)
        if map_to_base_link is not None:
            res['map_to_base_link'] = map_to_base_link[frame - 1];
        else:
            res['map_to_base_link'] = None;
        with open(os.path.join( annotations_dir, str(frame).zfill(6) + '.json'), mode='w') as frame:
            frame.write(json.dumps(res))
        return res

    @staticmethod
    def __get_annotation_image(automan_info, project_id, dataset_id, candidate_id, frame, ext, images_dir):
        path = '/projects/' + str(project_id) + '/datasets/' + str(dataset_id) \
            + '/candidates/' + str(candidate_id) + '/frames/' + str(frame) + '/'
        img_url = AutomanClient.send_get(automan_info, path).json()['image_link']
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
        if ext == '.jpg':
            return file_name
        return None

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
