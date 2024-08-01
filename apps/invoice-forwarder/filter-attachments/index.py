import re
import base64

def handler(inputs):
    additional_keywords = inputs.get('additional_keywords', [])
    def is_invoice_or_receipt(filename):
        invoice_keywords = ['invoice', 'inv', 'bill', "Rechnung", "Faktura"]
        receipt_keywords = ['receipt', "Quittung", "Beleg"]
        lower_filename = filename.lower()
        
        for keyword in invoice_keywords:
            if keyword in lower_filename:
                return 'invoice'
        for keyword in receipt_keywords:
            if keyword in lower_filename:
                return 'receipt'
        return None

    def search_keywords_in_text(text):
        # merge with additional_keywords
        keywords = ['invoice', 'inv', 'bill', "Rechnung", "Faktura", 'receipt', "Quittung", "Beleg"] + additional_keywords
        text = text.lower()
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                return True
        return False

    def extract_body_and_headers(message):
        body_data = message.get('body', {}).get('data', '')
        body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore') if body_data else ''
        headers = ' '.join([header['value'] for header in message.get('headers', [])])
        return body, headers

    def extract_content_recursive(parts, content_accumulator):
        for part in parts:
            if 'parts' in part:
                extract_content_recursive(part['parts'], content_accumulator)
            if 'body' in part and 'data' in part['body']:
                part_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                content_accumulator.append(part_body)
            if 'filename' in part and part['filename'].endswith('.pdf'):
                attachment_id = part['body'].get('attachmentId')
                if attachment_id:
                    attachment_type = is_invoice_or_receipt(part['filename'])
                    if attachment_type:
                        content_accumulator.append((attachment_id, attachment_type))
                    else:
                        content_accumulator.append((attachment_id, 'unknown'))

    def filter_attachments(message):
        body, headers = extract_body_and_headers(message['payload'])
        content_accumulator = [body, headers]

        parts = message['payload'].get('parts', [])
        extract_content_recursive(parts, content_accumulator)

        relevant_content = ' '.join([content for content in content_accumulator if isinstance(content, str)])
        content_has_keywords = search_keywords_in_text(relevant_content)

        pdf_attachments = [content for content in content_accumulator if isinstance(content, tuple)]

        # Filter out receipts if there are invoices
        invoices = [att for att in pdf_attachments if att[1] == 'invoice']
        receipts = [att for att in pdf_attachments if att[1] == 'receipt']
        unknowns = [att for att in pdf_attachments if att[1] == 'unknown']
        
        print("PDF Attachments:", pdf_attachments)
        print("Invoices:", invoices)
        print("Receipts:", receipts)
        print("Unknowns:", unknowns)
        print("Content has keywords:", content_has_keywords)
        if invoices:
            return [att[0] for att in invoices]
        elif receipts:
            return [att[0] for att in receipts]
        else:
            return [att[0] for att in unknowns if content_has_keywords]

    messages = inputs['messages']
    filtered_attachments = []

    for message in messages:
        message_id = message.get('id', 'unknown')
        attachment_ids = filter_attachments(message)
        # append attachment_ids to filtered_attachments directly but flat
        for attachment_id in attachment_ids:
            filtered_attachments.append({
                'message_id': message_id,
                'attachment_id': attachment_id
            })

    return {'filtered_attachments': filtered_attachments}

# Example usage:
# messages = [
#     {
#         "id": "message1",
#         "payload": {
#             "body": {
#                 "data": base64.urlsafe_b64encode(b'This is an invoice for your recent purchase.').decode('utf-8')
#             },
#             "headers": [
#                 {"name": "Subject", "value": "Your Invoice from Example Company"},
#                 {"name": "From", "value": "billing@example.com"}
#             ],
#             "parts": [
#                 {
#                     "filename": "invoice.pdf",
#                     "body": {
#                         "attachmentId": "ATTACHMENT_ID_1"
#                     }
#                 },
#                 {
#                     "filename": "receipt.pdf",
#                     "body": {
#                         "attachmentId": "ATTACHMENT_ID_2"
#                     }
#                 },
#                 {
#                     "filename": "document.pdf",
#                     "body": {
#                         "attachmentId": "ATTACHMENT_ID_3"
#                     }
#                 }
#             ]
#         }
#     },
#     {
#         "id": "message2",
#         "payload": {
#             "body": {
#                 "data": base64.urlsafe_b64encode(b'This is a receipt for your recent purchase.').decode('utf-8')
#             },
#             "headers": [
#                 {"name": "Subject", "value": "Your Receipt from Example Company"},
#                 {"name": "From", "value": "billing@example.com"}
#             ],
#             "parts": [
#                 {
#                     "filename": "receipt.pdf",
#                     "body": {
#                         "attachmentId": "ATTACHMENT_ID_4"
#                     }
#                 },
#                 {
#                     "filename": "document.pdf",
#                     "body": {
#                         "attachmentId": "ATTACHMENT_ID_5"
#                     }
#                 }
#             ]
#         }
#     }
# ]

# inputs = {"messages": messages}
# output = handler(inputs)
# print(output)
