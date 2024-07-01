import re
import base64

def handler(inputs):
    def filter_attachments(message):
        def is_invoice_or_receipt(filename):
            invoice_keywords = ['invoice', 'inv', 'bill']
            receipt_keywords = ['receipt', 'rcpt']
            lower_filename = filename.lower()
            
            for keyword in invoice_keywords:
                if keyword in lower_filename:
                    return 'invoice'
            for keyword in receipt_keywords:
                if keyword in lower_filename:
                    return 'receipt'
            return None

        def search_keywords_in_text(text):
            keywords = ['invoice', 'inv', 'bill', 'receipt', 'rcpt']
            text = text.lower()
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                    return True
            return False

        # Check if the body or header contains relevant keywords
        body = base64.urlsafe_b64decode(message['payload'].get('body', {}).get('data', '')).decode('utf-8', errors='ignore')
        headers = ' '.join([header['value'] for header in message['payload'].get('headers', [])])

        print("Body:", body)
        print("Headers:", headers)

        relevant_content = body + ' ' + headers
        content_has_keywords = search_keywords_in_text(relevant_content)

        parts = message['payload'].get('parts', [])
        pdf_attachments = []

        for part in parts:
            if part['filename'].endswith('.pdf'):
                attachment_id = part['body'].get('attachmentId')
                if attachment_id:
                    attachment_type = is_invoice_or_receipt(part['filename'])
                    if attachment_type:
                        pdf_attachments.append((attachment_id, attachment_type))
                    elif content_has_keywords:
                        pdf_attachments.append((attachment_id, 'unknown'))

        # Filter out receipts if there are invoices
        invoices = [att for att in pdf_attachments if att[1] == 'invoice']
        receipts = [att for att in pdf_attachments if att[1] == 'receipt']
        unknowns = [att for att in pdf_attachments if att[1] == 'unknown']
        
        print("PDF Attachments:", pdf_attachments)
        print("Invoices:", invoices)
        print("Receipts:", receipts)
        print("Unknowns:", unknowns)
        if invoices:
            return [att[0] for att in invoices]
        elif receipts:
            return [att[0] for att in receipts]
        else:
            return [att[0] for att in unknowns]

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
