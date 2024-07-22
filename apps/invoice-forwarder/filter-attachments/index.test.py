import unittest
import base64
from index import handler

class TestHandlerFunction(unittest.TestCase):

    def setUp(self):
        self.handler = handler

    def encode_body(self, body):
        return base64.urlsafe_b64encode(body.encode('utf-8')).decode('utf-8')

    def test_single_invoice(self):
        messages = [
            {
                "id": "message1",
                "payload": {
                    "body": {
                        "data": self.encode_body('This is an invoice for your recent purchase.')
                    },
                    "headers": [
                        {"name": "Subject", "value": "Your Invoice from Example Company"},
                        {"name": "From", "value": "billing@example.com"}
                    ],
                    "parts": [
                        {
                            "filename": "invoice.pdf",
                            "body": {
                                "attachmentId": "ATTACHMENT_ID_1"
                            }
                        }
                    ]
                }
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
                "payload": {
                    "body": {
                        "data": self.encode_body('This is a receipt for your recent purchase.')
                    },
                    "headers": [
                        {"name": "Subject", "value": "Your Receipt from Example Company"},
                        {"name": "From", "value": "billing@example.com"}
                    ],
                    "parts": [
                        {
                            "filename": "receipt.pdf",
                            "body": {
                                "attachmentId": "ATTACHMENT_ID_2"
                            }
                        }
                    ]
                }
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
                "payload": {
                    "body": {
                        "data": self.encode_body('This is an invoice for your recent purchase.')
                    },
                    "headers": [
                        {"name": "Subject", "value": "Your Invoice from Example Company"},
                        {"name": "From", "value": "billing@example.com"}
                    ],
                    "parts": [
                        {
                            "filename": "invoice.pdf",
                            "body": {
                                "attachmentId": "ATTACHMENT_ID_3"
                            }
                        },
                        {
                            "filename": "receipt.pdf",
                            "body": {
                                "attachmentId": "ATTACHMENT_ID_4"
                            }
                        },
                        {
                            "filename": "document.pdf",
                            "body": {
                                "attachmentId": "ATTACHMENT_ID_5"
                            }
                        }
                    ]
                }
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

    def test_recursive_body(self):
        messages = [
            {
                "id": "message4",
                "payload": {
                    "body": {
                        "data": self.encode_body('')
                    },
                    "headers": [
                        {"name": "Subject", "value": "Your Invoice from Example Company"},
                        {"name": "From", "value": "billing@example.com"}
                    ],
                    "parts": [
                        {
                            "mimeType": "multipart/alternative",
                            "parts": [
                                {
                                    "body": {
                                        "data": self.encode_body('This is an invoice for your recent purchase.')
                                    },
                                    "mimeType": "text/plain",
                                    "partId": "0.0"
                                },
                                {
                                    "body": {
                                        "data": self.encode_body('<p>This is an invoice for your recent purchase.</p>')
                                    },
                                    "mimeType": "text/html",
                                    "partId": "0.1"
                                }
                            ]
                        },
                        {
                            "filename": "invoice.pdf",
                            "body": {
                                "attachmentId": "ATTACHMENT_ID_6"
                            }
                        }
                    ]
                }
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
                "payload": {
                    "body": {
                        "data": self.encode_body('This is a document.')
                    },
                    "headers": [
                        {"name": "Subject", "value": "Your Document from Example Company"},
                        {"name": "From", "value": "info@example.com"}
                    ],
                    "parts": [
                        {
                            "filename": "document.pdf",
                            "body": {
                                "attachmentId": "ATTACHMENT_ID_7"
                            }
                        }
                    ]
                }
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
