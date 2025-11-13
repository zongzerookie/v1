import requests
import os
import json
# import time  # <- 已移除 time 模块，因为不再需要

def ocr_space_file(filename, overlay=True, api_key='K88316391788957', language='eng'):
    """ OCR.space API request with local file. """
    payload = {'isOverlayRequired': overlay,
               'apikey': api_key,
               'language': language,
               'OCRengine': 2
               }
    try:
        with open(filename, 'rb') as f:
            r = requests.post('https://api.ocr.space/parse/image',
                              files={filename: f},
                              data=payload,
                              timeout=30)  # 增加超时以防卡住

        # 检查 403 速率限制错误或其它 HTTP 错误
        if r.status_code == 403:
            print(f"❌ 收到 403 禁止访问错误。很可能已达到 API 速率限制。")
            print(f"服务器消息: {r.text}")
            return None  # 返回 None 表示失败
        elif r.status_code != 200:
            print(f"❌ 收到非 200 状态码: {r.status_code}。消息: {r.text}")
            return None

        return r.content.decode()
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return None


def get_img_list(file_path):
    img_list = [img for img in os.listdir(file_path) if not os.path.isdir(img) and img.endswith('png')]
    img_list.sort()
    return img_list


def is_alpha(character):
    if not character or len(character) == 0:
        return False
    return 'a' <= character[0].lower() <= 'z'


def is_existing(character, img_info):
    for char_dict in img_info:
        if char_dict.get('WordText') == character:
            return 0  # 已存在
    return 1  # 不存在


def write_info(info_json, img_key, json_dict):
    """
    (修改版) 保存所有识别到的文本词汇及其坐标。
    """
    img_info = []

    if not info_json or not info_json.get('ParsedResults') or len(info_json['ParsedResults']) == 0:
        print(f"警告: 图像 {img_key} 的OCR结果为空或格式不正确。")
        json_dict[img_key] = []
        return

    parsed_results = info_json['ParsedResults'][0]

    if 'TextOverlay' not in parsed_results or not parsed_results['TextOverlay']['Lines']:
        print(f"警告: 图像 {img_key} 未找到文本行 (TextOverlay 为空)。")
        json_dict[img_key] = []
        return

    # 遍历所有识别到的“行”
    for line_text in parsed_results['TextOverlay']['Lines']:
        # 遍历该行中的所有“词”
        if not line_text.get('Words'):
            continue

        for word_info in line_text['Words']:
            word_text = word_info.get('WordText')

            # 只要识别出了文本，就保存它
            if word_text:
                char_dict = {
                    'WordText': word_text,
                    'Coordinate': {
                        'Center': (
                        word_info['Left'] + word_info['Width'] / 2, word_info['Top'] + word_info['Height'] / 2),
                        'Left': word_info['Left'],
                        'Top': word_info['Top'],
                        'Height': word_info['Height'],
                        'Width': word_info['Width']
                    }
                }
                img_info.append(char_dict)

    json_dict[img_key] = img_info


if __name__ == '__main__':
    # 1. 定义路径
    base_data_dir = r'D:\代码\2019-mytqa-master\data'

    # 定义统一的输出目录
    output_dir = os.path.join(base_data_dir, 'processed_data', 'ocr_results')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"OCR 结果将集中保存到: {output_dir}")

    # 2. 定义要处理的 slice 和 文件夹
    slice_path_list = ['train', 'val', 'test']
    image_folder_list = ['abc_question_images', 'question_images', 'teaching_images', 'textbook_images']

    # 3. 遍历 Slices (train, val, test)
    for slice_path in slice_path_list:
        print(f"\n----- 开始处理 {slice_path} 数据集 -----")

        # 4. 为每个 slice 定义一个独立的 JSON 输出文件
        img_info_json_path = os.path.join(output_dir, f'{slice_path}_ocr_results.json')

        # 5. 增量处理：如果json文件已存在，先读取已有内容
        json_dict = {}
        if os.path.exists(img_info_json_path):
            try:
                with open(img_info_json_path, 'r', encoding='utf-8') as f:
                    json_dict = json.load(f)
                    print(f"已加载 {len(json_dict)} 条已有记录 from {img_info_json_path}")
            except json.JSONDecodeError:
                print(f"警告: {img_info_json_path} 文件已损坏，将重新创建。")
                json_dict = {}

        # 6. 遍历所有图像文件夹 (abc_question_images, question_images, ...)
        for image_folder_name in image_folder_list:
            img_dir_path = os.path.join(base_data_dir, slice_path, image_folder_name)

            if not os.path.exists(img_dir_path):
                print(f"目录不存在，跳过: {img_dir_path}")
                continue

            print(f"\n--- 正在扫描子文件夹: {img_dir_path} ---")
            img_list = get_img_list(img_dir_path)

            total_images = len(img_list)
            if total_images == 0:
                print("未找到 .png 图片，跳过。")
                continue

            # 7. 遍历文件夹中的所有图片
            for i, img in enumerate(img_list):

                # 8. 创建唯一键 (例如: "question_images/L_0001_Q_0001.png")
                img_key = os.path.join(image_folder_name, img).replace("\\", "/")  # 确保使用正斜杠

                # 9. 增量检查：如果图片已经处理过，则跳过
                if img_key in json_dict:
                    print(f"  已跳过 ({i + 1}/{total_images}): {img_key}")
                    continue

                print(f"  正在处理图像 ({i + 1}/{total_images}): {img_key}")
                full_img_path = os.path.join(img_dir_path, img)
                info_str = ocr_space_file(full_img_path)

                # 10. 速率限制处理
                if info_str is None:  # 如果 API 请求失败 (例如 403)
                    print("OCR 请求失败，脚本将终止。请检查您的 API 密钥限制，等待一段时间后再试。")
                    # 保存当前进度并退出
                    try:
                        with open(img_info_json_path, 'w', encoding='utf-8') as f:
                            json.dump(json_dict, f, indent=4, ensure_ascii=False)
                        print(f"已将当前 {len(json_dict)} 条进度保存到 {img_info_json_path}")
                    except Exception as e:
                        print(f"保存进度时出错: {e}")
                    exit()  # 直接退出程序

                # 11. 解析和保存结果
                try:
                    info_json = json.loads(info_str)
                except json.JSONDecodeError:
                    print(f"  错误: 无法解析 {img_key} 的 OCR 响应: {info_str[:100]}...")
                    continue  # 跳过这张损坏的图片

                if info_json.get('IsErroredOnProcessing'):
                    print(f"  错误: OCR处理失败 for {img_key}. 原因: {info_json.get('ErrorMessage')}")
                else:
                    write_info(info_json, img_key, json_dict)

                # 12. 礼貌性等待 (已移除)
                # print("  等待 3 秒以避免 API 速率限制...")
                # time.sleep(3)

        # 13. 在处理完一个 slice (train/val/test) 的所有文件夹后，统一写入文件
        try:
            with open(img_info_json_path, 'w', encoding='utf-8') as f:
                json.dump(json_dict, f, indent=4, ensure_ascii=False)
            print(f"\n成功为 {slice_path} 数据集生成/更新 {img_info_json_path}")
        except Exception as e:
            print(f"写入 JSON 文件时发生严重错误: {e}")