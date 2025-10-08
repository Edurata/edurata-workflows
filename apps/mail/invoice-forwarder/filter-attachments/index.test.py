import unittest
from index import handler

class TestHandlerFunction(unittest.TestCase):

    def setUp(self):
        self.handler = handler

    def test_single_invoice(self):
        messages = [
            {
                "id": "message1",
                "subject": "Your Invoice from Example Company",
                "from": {
                    "emailAddress": {
                        "address": "billing@example.com"
                    }
                },
                "body": {
                    "content": "<html>This is an invoice for your recent purchase.</html>",
                    "contentType": "html"
                },
                "attachments": [
                    {
                        "id": "ATTACHMENT_ID_1",
                        "name": "invoice.pdf",
                        "contentType": "application/pdf"
                    }
                ]
            }
        ]
        inputs = {"messages": messages}
        output = self.handler(inputs)
        expected_output = {
            'filtered_attachments': [
                {'message_id': 'message1', 'attachment_id': 'ATTACHMENT_ID_1'}
            ]
        }
        self.assertEqual(output, expected_output)

    def test_single_receipt(self):
        messages = [
            {
                "id": "message2",
                "subject": "Your Receipt from Example Company",
                "from": {
                    "emailAddress": {
                        "address": "billing@example.com"
                    }
                },
                "body": {
                    "content": "<html>This is a receipt for your recent purchase.</html>",
                    "contentType": "html"
                },
                "attachments": [
                    {
                        "id": "ATTACHMENT_ID_2",
                        "name": "receipt.pdf",
                        "contentType": "application/pdf"
                    }
                ]
            }
        ]
        inputs = {"messages": messages}
        output = self.handler(inputs)
        expected_output = {
            'filtered_attachments': [
                {'message_id': 'message2', 'attachment_id': 'ATTACHMENT_ID_2'}
            ]
        }
        self.assertEqual(output, expected_output)

    def test_multiple_attachments(self):
        messages = [
            {
                "id": "message3",
                "subject": "Your Invoice from Example Company",
                "from": {
                    "emailAddress": {
                        "address": "billing@example.com"
                    }
                },
                "body": {
                    "content": "<html>This is an invoice for your recent purchase.</html>",
                    "contentType": "html"
                },
                "attachments": [
                    {
                        "id": "ATTACHMENT_ID_3",
                        "name": "invoice.pdf",
                        "contentType": "application/pdf"
                    },
                    {
                        "id": "ATTACHMENT_ID_4",
                        "name": "receipt.pdf",
                        "contentType": "application/pdf"
                    },
                    {
                        "id": "ATTACHMENT_ID_5",
                        "name": "document.pdf",
                        "contentType": "application/pdf"
                    }
                ]
            }
        ]
        inputs = {"messages": messages}
        output = self.handler(inputs)
        expected_output = {
            'filtered_attachments': [
                {'message_id': 'message3', 'attachment_id': 'ATTACHMENT_ID_3'}
            ]
        }
        self.assertEqual(output, expected_output)

    def test_html_body_with_invoice_keyword(self):
        messages = [
            {
                "id": "message4",
                "subject": "Your Invoice from Example Company",
                "from": {
                    "emailAddress": {
                        "address": "billing@example.com"
                    }
                },
                "body": {
                    "content": "<html><p>This is an invoice for your recent purchase.</p></html>",
                    "contentType": "html"
                },
                "attachments": [
                    {
                        "id": "ATTACHMENT_ID_6",
                        "name": "invoice.pdf",
                        "contentType": "application/pdf"
                    }
                ]
            }
        ]
        inputs = {"messages": messages}
        output = self.handler(inputs)
        expected_output = {
            'filtered_attachments': [
                {'message_id': 'message4', 'attachment_id': 'ATTACHMENT_ID_6'}
            ]
        }
        self.assertEqual(output, expected_output)

    def test_no_relevant_attachments(self):
        messages = [
            {
                "id": "message5",
                "subject": "Your Document from Example Company",
                "from": {
                    "emailAddress": {
                        "address": "info@example.com"
                    }
                },
                "body": {
                    "content": "<html>This is a document.</html>",
                    "contentType": "html"
                },
                "attachments": [
                    {
                        "id": "ATTACHMENT_ID_7",
                        "name": "document.pdf",
                        "contentType": "application/pdf"
                    }
                ]
            }
        ]
        inputs = {"messages": messages}
        output = self.handler(inputs)
        expected_output = {
            'filtered_attachments': []
        }
        self.assertEqual(output, expected_output)

if __name__ == '__main__':
    unittest.main()
