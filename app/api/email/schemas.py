from pydantic import BaseModel

class EmailReplyRequest(BaseModel):
    reply_body: str


class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str