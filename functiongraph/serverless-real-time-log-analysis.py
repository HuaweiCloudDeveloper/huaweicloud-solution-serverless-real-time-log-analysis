# -*- coding: utf-8 -*-
import json
import time
import random
import base64
from obs import ObsClient
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdksmn.v2.region.smn_region import SmnRegion
from huaweicloudsdksmn.v2 import SmnClient, PublishMessageRequestBody, PublishMessageRequest


LOGGER_PREFIX = "log"
ALARM_LOG_KEY = ["WARN", "WRN", "ERROR", "ERR"]
SMN_SUBJECT = "FunctionGraph Log Analysis Alarm"


def handler(event, context):
    log = context.getLogger()
    obs_address = context.getUserData("obs_address")
    obs_bucket = context.getUserData("obs_store_bucket")
    if not obs_address or not obs_bucket:
        raise Exception("Please configure obs environment variable")
    if not context.getAccessKey() or not context.getSecretKey():
        raise Exception(
            "Can not get accessKey or secretKey. Please check agency")
    if not context.getUserData('smn_urn'):
        raise Exception("Please configure SMN  environment variable")
    encodingData = event["lts"]["data"]
    data_based = base64.b64decode(encodingData)
    data = json.loads(data_based)
    log.info(
        f"log group id [{data['log_group_id']}], topic id [{data['log_topic_id']}] ")
    print("data: ",data )
    logs = data["logs"]
    alarm_logs = analyze_logs(logs)
    print("==========================")
    print(logs)
    print("==========================")
    print(alarm_logs)
    if len(alarm_logs) == 0:
        log.info("no need alarm")
        return "no need alarm"

    object_name = gen_log_name()
    logs_str = json.dumps(alarm_logs).replace('\\', '')
    obs_clinet = new_obs_client(context, obs_address)
    res = upload_content_to_obs(obs_clinet, obs_bucket, logs_str, object_name)
    log_obs_path = f"check Full log at obs [{object_name}]"
    if not res:
        log_obs_path = f"check full log at FGS log"
    smn_client = new_smn_client(context)
    send_smn_msg(context, smn_client, logs_str, log_obs_path)
    return 'alarm success'


def analyze_logs(logs):
    alarm_logs = []
    if type(logs) != list:
        logs = json.loads(logs) 
    for log in logs:
        log_str = json.dumps(log)
        print("one lg :", log_str)
        for item in ALARM_LOG_KEY:
            if item in log_str:
                alarm_logs.append(log_str)
                break
    return alarm_logs


def gen_log_name():
    t = time.strftime("%Y%m%d%H%M%S")
    return f"{LOGGER_PREFIX}/log-{t}-{random.randint(100000,1000000)}.log"


def new_obs_client(context, obs_server):
    return ObsClient(
        access_key_id=context.getAccessKey(),
        secret_access_key=context.getSecretKey(),
        server=obs_server
    )


def upload_content_to_obs(client: ObsClient, bucket_name, content, obj_name):
    try:
        resp = client.putContent(bucket_name, obj_name, content=content)
        if resp.status > 300:
            print('errorCode:', resp.errorCode)
            print('errorMessage:', resp.errorMessage)
            print("=========source log============")
            print(content)
            return False
    except:
        import traceback
        print(traceback.format_exc())
        print("=========source log============")
        print(content)
        return False
    return True


def new_smn_client(context):
    my_region = context.getUserData("smn_urn").split(':')[2]
    credentials = BasicCredentials(
        context.getAccessKey(), context.getSecretKey(),context.getProjectID())
    client = SmnClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(SmnRegion.value_of(my_region)) \
        .build()
    return client


def send_smn_msg(context, client, logs_str, log_obs_path):
    print("start to send")
    request = PublishMessageRequest()
    request.topic_urn = context.getUserData("smn_urn")
    request.body = PublishMessageRequestBody(
        subject=SMN_SUBJECT,
        message=f"{SMN_SUBJECT} | {log_obs_path}  : {logs_str}"
    )
    resp = client.publish_message(request)
    print("smn esp :", resp)