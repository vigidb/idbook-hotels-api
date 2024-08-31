#! /usr/bin/python3
import os
from time import gmtime, strftime, ctime, localtime
import smtplib, ssl
import mimetypes
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from time import gmtime, strftime, localtime


EMAIL_SENDER = "noreply@idbookhotels.com"
EMAIL_SENDER_PASSWORD = "ctqmvaaydtjxyudi"
RECEIVERS_EMAIL = ["atuladya.com@gmail.com"]

email_from, password = EMAIL_SENDER, EMAIL_SENDER_PASSWORD

# email_list = RECEIVERS_EMAIL

def list_to_string(input_list):
    initial_string = ","
    return initial_string.join(input_list)


def email_sender(receivers_email, email_subject, html_body, cc_email=None,
                 bcc_email=None, reply_to=None, file_to_send=None, file_path=None):
    msg = MIMEMultipart()
    msg["From"] = email_from
    msg["To"] = list_to_string(receivers_email)
    msg["Subject"] = email_subject

    if cc_email is not None:
       msg["Cc"] = list_to_string(cc_email)

    if reply_to is not None:
        msg.add_header('reply-to', reply_to)

    if html_body is not None:
        part = MIMEText(html_body, "html")
        msg.attach(part)

    if file_path is not None:
        c_type, encoding = mimetypes.guess_type(file_path)
        if c_type is None or encoding is not None:
            c_type = "application/octet-stream"

        maintype, subtype = c_type.split("/", 1)

        if maintype == "text":
            fp = open(file_path)
            # Note: we should handle calculating the charset
            attachment = MIMEText(fp.read(), _subtype=subtype)
            fp.close()
        elif maintype == "image":
            fp = open(file_path, "rb")
            attachment = MIMEImage(fp.read(), _subtype=subtype)
            fp.close()
        elif maintype == "audio":
            fp = open(file_path, "rb")
            attachment = MIMEAudio(fp.read(), _subtype=subtype)
            fp.close()
        else:
            fp = open(file_path, "rb")
            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(fp.read())
            fp.close()
            encoders.encode_base64(attachment)
        attachment.add_header("Content-Disposition", "attachment", filename=file_to_send)
        msg.attach(attachment)

    server = smtplib.SMTP("smtp.gmail.com:587")
    server.starttls()
    server.login(email_from, password)

    if (cc_email and bcc_email) is not None:
        server.sendmail(email_from, receivers_email + cc_email + bcc_email, msg.as_string())
        server.quit()
        print("{} mail sent successfully to {}".format(strftime("%d-%m-%Y %H:%M:%S", localtime()),
                                                       receivers_email + cc_email + bcc_email))
    elif cc_email is not None:
        server.sendmail(email_from, receivers_email + cc_email, msg.as_string())
        server.quit()
        print("{} mail sent successfully to {}".format(strftime("%d-%m-%Y %H:%M:%S", localtime()),
                                                       receivers_email + cc_email))


    elif bcc_email is not None:
        server.sendmail(email_from, receivers_email + bcc_email, msg.as_string())
        server.quit()
        print("{} mail sent successfully to {}".format(strftime("%d-%m-%Y %H:%M:%S", localtime()),
                                                       receivers_email + bcc_email))
    else:
        server.sendmail(email_from, receivers_email, msg.as_string())
        server.quit()
        print("{} mail sent successfully to {}".format(strftime("%d-%m-%Y %H:%M:%S", localtime()), receivers_email))


subject = "test"
html_body = """
<p>Dear {},</p>
<p>Congratulations on your joining us, </p>
"""

email_sender(RECEIVERS_EMAIL, subject, html_body,)
