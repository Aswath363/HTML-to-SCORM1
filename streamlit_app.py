# Streamlit app: Convert HTML (or a folder/zip) into a SCORM 1.2 package (zip)
# Save this file as `html_to_scorm_streamlit.py` and run: `streamlit run html_to_scorm_streamlit.py`

import streamlit as st
import tempfile
import zipfile
import os
import uuid
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

st.set_page_config(page_title="HTML → SCORM (1.2)", layout="wide")
st.title("HTML → SCORM 1.2 package maker")
st.write("Upload a single HTML file, or a ZIP containing a web course (HTML/CSS/JS/assets). This app will wrap it into a minimal SCORM 1.2 package for LMS import.")

# --- Helpers ---

def generate_manifest(title, identifier, launch_file, file_list):
    NS = {
        '': 'http://www.imsglobal.org/xsd/imscp_v1p1',
        'adlcp': 'http://www.adlnet.org/xsd/adlcp_v1p3',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }
    ET.register_namespace('', NS[''])
    ET.register_namespace('adlcp', NS['adlcp'])
    ET.register_namespace('xsi', NS['xsi'])

    manifest = ET.Element('manifest', {
        'identifier': identifier,
        'version': '1'
    })

    metadata = ET.SubElement(manifest, 'metadata')
    schema = ET.SubElement(metadata, 'schema')
    schema.text = 'ADL SCORM'
    schemav = ET.SubElement(metadata, 'schemaversion')
    schemav.text = '1.2'

    organizations = ET.SubElement(manifest, 'organizations', {'default': 'ORG-1'})
    org = ET.SubElement(organizations, 'organization', {'identifier': 'ORG-1'})
    title_el = ET.SubElement(org, 'title')
    title_el.text = title
    item = ET.SubElement(org, 'item', {'identifier': 'ITEM-1', 'identifierref': 'RES-1'})
    item_title = ET.SubElement(item, 'title')
    item_title.text = title

    resources = ET.SubElement(manifest, 'resources')
    res = ET.SubElement(resources, 'resource', {
        'identifier': 'RES-1',
        'type': 'webcontent',
        '{http://www.adlnet.org/xsd/adlcp_v1p3}scormtype': 'sco',
        'href': launch_file
    })

    for f in sorted(file_list):
        ET.SubElement(res, 'file', {'href': f.replace('\\', '/')})

    xml_bytes = ET.tostring(manifest, encoding='utf-8', method='xml')
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes

# --- UI inputs ---
course_title = st.text_input('Course title', value='My HTML Course')
uploaded = st.file_uploader('Upload a single HTML file or a ZIP (containing course files)', type=['html', 'htm', 'zip'])

scorm_id = f"com.example.scorm.{uuid.uuid4().hex[:8]}"

if uploaded:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        uploaded_path = tmpdir_path / uploaded.name
        with open(uploaded_path, 'wb') as f:
            f.write(uploaded.getbuffer())

        course_root = tmpdir_path / 'course'
        course_root.mkdir(exist_ok=True)

        if uploaded.name.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(uploaded_path, 'r') as z:
                    z.extractall(course_root)
            except zipfile.BadZipFile:
                st.error('Uploaded file is not a valid ZIP.')
                st.stop()
        else:
            target_name = 'index.html'
            if uploaded.name.lower().endswith(('index.html', 'index.htm')):
                target_name = uploaded.name
            with open(course_root / target_name, 'wb') as f:
                f.write(uploaded_path.read_bytes())

        html_files = list(course_root.rglob('*.html')) + list(course_root.rglob('*.htm'))
        if not html_files:
            st.error('No HTML files found in uploaded content.')
            st.stop()

        root_index = course_root / 'index.html'
        if root_index.exists():
            launch_file = 'index.html'
        else:
            rel = html_files[0].relative_to(course_root)
            launch_file = str(rel).replace('\\', '/')

        file_list = []
        for p in course_root.rglob('*'):
            if p.is_file():
                rel = p.relative_to(course_root)
                file_list.append(str(rel).replace('\\', '/'))

        manifest_bytes = generate_manifest(course_title, scorm_id, launch_file, file_list)

        mem_zip = BytesIO()
        with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for p in course_root.rglob('*'):
                if p.is_file():
                    arcname = str(p.relative_to(course_root)).replace('\\', '/')
                    zf.write(p, arcname)
            zf.writestr('imsmanifest.xml', manifest_bytes)

        mem_zip.seek(0)
        pkg_name = f"{course_title.strip().replace(' ', '_')}_SCORM.zip"

        st.success('SCORM package created successfully!')
        st.download_button('Download SCORM package', data=mem_zip.getvalue(), file_name=pkg_name, mime='application/zip')
else:
    st.info('Upload an HTML file (.html/.htm) or a ZIP of your course to begin.')
