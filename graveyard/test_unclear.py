from bs4 import NavigableString, Tag, BeautifulSoup

def extract_text_with_metadata_v2(element, metadata_stack=None, pending_metadata=None, results=None):
    if metadata_stack is None:
        metadata_stack = []
    if pending_metadata is None:
        pending_metadata = {}
    if results is None:
        results = []
    
    if isinstance(element, NavigableString):
        text = str(element)
        if text.strip():  # Only add non-empty text
            current_metadata = {}
            for meta in metadata_stack:
                current_metadata.update(meta)
            current_metadata.update(pending_metadata)
            results.append((text, current_metadata.copy()))
            pending_metadata.clear()  # Clear after applying to the first text node
        return results, pending_metadata
        
    if isinstance(element, Tag):
        tag_metadata = {}
        if element.name == 'unclear':
            tag_metadata['unclear'] = True
            if element.get('reason'):
                tag_metadata['unclear_reason'] = element.get('reason')
        if element.name == 'add':
            tag_metadata['add'] = True
            if element.get('hand'):
                tag_metadata['add_hand'] = element.get('hand')
                
        if tag_metadata:
            metadata_stack.append(tag_metadata)
            
        has_children = False
        for child in element.children:
            has_children = True
            extract_text_with_metadata_v2(child, metadata_stack, pending_metadata, results)
            
        if not has_children and tag_metadata:
            pending_metadata.update(tag_metadata)
            
        if tag_metadata:
            metadata_stack.pop()
            
    return results, pending_metadata

soup = BeautifulSoup("<p>text1 <unclear reason=\"damage\"/> text2</p>", "xml")
results, _ = extract_text_with_metadata_v2(soup)
print(results)
