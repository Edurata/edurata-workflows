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
            lowered_keyword = keyword.lower()
            if re.search(r'\b' + re.escape(lowered_keyword) + r'\b', text):
                return True
        return False

    def extract_body_and_subject(message):
        # Microsoft Graph API format
        body_content = message.get('body', {}).get('content', '')
        subject = message.get('subject', '')
        return body_content, subject

    def filter_attachments(message):
        # Extract body and subject for Microsoft Graph API
        body, subject = extract_body_and_subject(message)
        content_accumulator = [body, subject]
        
        # Get sender email
        from_email = message.get('from', {}).get('emailAddress', {}).get('address', '')
        content_accumulator.append(from_email)

        # Process attachments from Microsoft Graph API
        attachments = message.get('attachments', [])
        pdf_attachments = []
        
        for attachment in attachments:
            filename = attachment.get('name', '')
            attachment_id = attachment.get('id', '')
            content_type = attachment.get('contentType', '')
            
            # Check if it's a PDF
            if content_type == 'application/pdf' or filename.lower().endswith('.pdf'):
                attachment_type = is_invoice_or_receipt(filename)
                if attachment_type:
                    pdf_attachments.append((attachment_id, attachment_type))
                else:
                    pdf_attachments.append((attachment_id, 'unknown'))

        relevant_content = ' '.join(content_accumulator)
        content_has_keywords = search_keywords_in_text(relevant_content)

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

# Example usage (Microsoft Graph API format):
# messages = [
#     {
#         "id": "message1",
#         "subject": "Your Invoice from Example Company",
#         "from": {
#             "emailAddress": {
#                 "address": "billing@example.com"
#             }
#         },
#         "body": {
#             "content": "<html>This is an invoice for your recent purchase.</html>",
#             "contentType": "html"
#         },
#         "attachments": [
#             {
#                 "id": "ATTACHMENT_ID_1",
#                 "name": "invoice.pdf",
#                 "contentType": "application/pdf"
#             },
#             {
#                 "id": "ATTACHMENT_ID_2",
#                 "name": "receipt.pdf",
#                 "contentType": "application/pdf"
#             },
#             {
#                 "id": "ATTACHMENT_ID_3",
#                 "name": "document.pdf",
#                 "contentType": "application/pdf"
#             }
#         ]
#     },
#     {
#         "id": "message2",
#         "subject": "Your Receipt from Example Company",
#         "from": {
#             "emailAddress": {
#                 "address": "billing@example.com"
#             }
#         },
#         "body": {
#             "content": "<html>This is a receipt for your recent purchase.</html>",
#             "contentType": "html"
#         },
#         "attachments": [
#             {
#                 "id": "ATTACHMENT_ID_4",
#                 "name": "receipt.pdf",
#                 "contentType": "application/pdf"
#             },
#             {
#                 "id": "ATTACHMENT_ID_5",
#                 "name": "document.pdf",
#                 "contentType": "application/pdf"
#             }
#         ]
#     }
# ]

# inputs = {"messages": messages}
# output = handler(inputs)
# print(output)
