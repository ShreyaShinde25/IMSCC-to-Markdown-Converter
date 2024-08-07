import zipfile
import os
import xml.etree.ElementTree as ET
import json
from bs4 import BeautifulSoup
from pprint import pprint
from html import unescape
import html2text




def extract_imscc(file_path, extract_to):
    with zipfile.ZipFile(file_path, 'r') as imscc_zip:
        imscc_zip.extractall(extract_to)
    return extract_to

def parse_manifest(manifest_path):
    tree = ET.parse(manifest_path)
    root = tree.getroot()

    namespaces = {
        'default': 'http://www.imsglobal.org/xsd/imsccv1p3/imscp_v1p1',
        'lomr': 'http://ltsc.ieee.org/xsd/imsccv1p3/LOM/resource',
        'lomm': 'http://ltsc.ieee.org/xsd/imsccv1p3/LOM/manifest',
    }

    def parse_item(item):
        title_element = item.find('default:title', namespaces)
        title = title_element.text if title_element is not None else 'No Title'
        identifier = item.attrib['identifier']
        resource = item.attrib.get('identifierref', None)
        children = [parse_item(child) for child in item.findall('default:item', namespaces)]
        return {
            'title': title,
            'identifier': identifier,
            'resource': resource,
            'children': children
        }

    organization = root.find('default:organizations/default:organization', namespaces)
    parsed_hierarchy = [parse_item(item) for item in organization.findall('default:item', namespaces)]

    resource_map = {}
    for resource in root.findall('default:resources/default:resource', namespaces):
        resource_id = resource.attrib['identifier']
        file_element = resource.find('default:file', namespaces)
        if file_element is not None:
            file_path = file_element.attrib['href']
            resource_map[resource_id] = file_path

    return parsed_hierarchy, resource_map

def read_resource_file(resource_file_path):
    with open(resource_file_path, 'rb') as f:
        content = f.read()
    try:
        soup = BeautifulSoup(content, 'html.parser')
        return soup.get_text()
    except UnicodeDecodeError:
        return None

def read_weblinks_file(weblink_path):
    tree = ET.parse(weblink_path)
    root = tree.getroot()
    title= root.find('{http://www.imsglobal.org/xsd/imsccv1p3/imswl_v1p3}title').text
    url_element=root.find('{http://www.imsglobal.org/xsd/imsccv1p3/imswl_v1p3}url')
    url_href = url_element.attrib['href']
    # print("title:",title)
    # print("url:",url_href)
    content = f"Title: {title}\nURL: {url_href}\n\n"
    return content

def read_discussion_file(discussion_path):
    print(discussion_path)
    tree = ET.parse(discussion_path)
    root = tree.getroot()
    title= root.find('{http://www.imsglobal.org/xsd/imsccv1p3/imsdt_v1p3}title').text
    text=root.find('{http://www.imsglobal.org/xsd/imsccv1p3/imsdt_v1p3}text')
    print(title)
    print(text)

def read_quiz_file(quiz_path):
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True

    tree = ET.parse(quiz_path)
    root = tree.getroot()
    namespace = {'ns': 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2'}

    # Extract assessment title
    assessment = root.find('ns:assessment', namespace)
    assessment_title = assessment.attrib.get('title', 'No Title')

    # Extract metadata fields
    metadata = assessment.find('ns:qtimetadata', namespace)
    metadata_fields = {}
    for field in metadata.findall('ns:qtimetadatafield', namespace):
        label = field.find('ns:fieldlabel', namespace).text
        entry = field.find('ns:fieldentry', namespace).text
        metadata_fields[label] = entry

    # Extract questions and choices
    questions = []
    section = assessment.find('ns:section', namespace)
    for item in section.findall('ns:item', namespace):
        question_data = {}
        
        # Extract question text
        presentation = item.find('ns:presentation', namespace)
        material = presentation.find('ns:material', namespace)
        question_text = material.find('ns:mattext', namespace).text
        # question_data['question'] = unescape(question_text)
        question_data['question'] = h.handle(unescape(question_text)).strip()
        
        
        # Extract choices
        choices = []
        response_lid = presentation.find('ns:response_lid', namespace)
        render_choice = response_lid.find('ns:render_choice', namespace)
        for response_label in render_choice.findall('ns:response_label', namespace):
            material = response_label.find('ns:material', namespace)
            choice_text = material.find('ns:mattext', namespace).text
            # choices.append(unescape(choice_text))
            choices.append(h.handle(unescape(choice_text)).strip())
        
        question_data['choices'] = choices
        questions.append(question_data)

        content= f"Assessment Title: {assessment_title}\nMetadata Fields: {metadata_fields}\nQuestions: {questions}\n\n"
        return content

def build_book_structure(hierarchy, resource_map, resources_folder):
    book_content = []

    def traverse_hierarchy(items, level=1):
        for item in items:
            title = item['title']
            resource = item['resource']
            # print(f"{'#' * level} {title}\n\n")
            book_content.append(f"{'#' * level} {title}\n\n")
            if resource:
                resource_file = resource_map.get(resource)
                if resource_file:
                    resource_file_path = os.path.join(resources_folder, resource_file)
                    if os.path.exists(resource_file_path):
                        # print(resource_file_path)
                        if(resource_file_path.find('weblinks')!=-1):
                            book_content.append(read_weblinks_file(resource_file_path)+ "\n\n")
                        elif(resource_file_path.find('quiz')!=-1):
                            book_content.append(read_quiz_file(resource_file_path)+"\n\n")
                        elif resource_file_path.lower().endswith('.html'):
                            book_content.append(read_resource_file(resource_file_path)+"\n\n")
                    # if content:
                    #     book_content.append(content + "\n\n")
            if item['children']:
                traverse_hierarchy(item['children'], level + 1)

    traverse_hierarchy(hierarchy)
    return ''.join(book_content)

def save_as_text(data, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(data)

if __name__ == "__main__":
    imscc_file_path = 'file.imscc'
    extract_to = 'extracted_content'
    manifest_file_name = 'imsmanifest.xml'
    output_text_path = 'output_book.md'

    # Step 1: Extract the imscc file
    extract_imscc(imscc_file_path, extract_to)

    # Step 2: Parse the manifest file
    manifest_path = os.path.join(extract_to, manifest_file_name)
    hierarchy_data, resource_map = parse_manifest(manifest_path)

    # pprint(hierarchy_data)

    # Step 3: Build the book structure
    resources_folder = extract_to  # Folder where the resource files are located
    book_content = build_book_structure(hierarchy_data, resource_map, resources_folder)

    # Step 4: Save the book content as a text file
    save_as_text(book_content, output_text_path)

    print(f"Book has been successfully saved to {output_text_path}")
