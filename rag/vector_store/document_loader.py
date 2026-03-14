from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
import os

def load_documents(base_path=None):
    if base_path is None:
        base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    
    docs = []
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".md"):
                path = os.path.join(root, file)
                loader = TextLoader(path, encoding="utf-8")
                document = loader.load()[0]
                # store both the filename and the relative path (folder/file)
                rel_path = os.path.relpath(path, base_path).replace('\\', '/')
                document.metadata["source"] = file
                document.metadata["path"] = rel_path
                # folder (top-level folder under data) in lowercase for easy matching
                folder = rel_path.split('/')[0] if '/' in rel_path else ''
                document.metadata["folder"] = folder.lower()
                docs.append(document)
    return docs
