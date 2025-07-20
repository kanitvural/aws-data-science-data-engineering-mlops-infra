import json
import boto3
import os

def lambda_handler(event, context):
    sns = boto3.client('sns')
    topic_arn = os.environ['SNS_TOPIC_ARN']
    project_name = os.environ['PROJECT_NAME']
    
    # EventBridge'den gelen event'i parse et
    detail = event.get('detail', {})
    job_name = detail.get('jobName', 'Unknown')
    state = detail.get('state', 'Unknown')
    job_run_id = detail.get('jobRunId', 'Unknown')
    
    # Mesajı oluştur
    if state == 'SUCCEEDED':
        subject = f"✅ Glue Job Başarılı - {project_name}"
        message = f"""
Glue Job başarıyla tamamlandı!

📊 Job Detayları:
- Job Adı: {job_name}
- Durum: {state}
- Job Run ID: {job_run_id}
- Proje: {project_name}

Zaman: {event.get('time', 'Unknown')}
"""
    elif state == 'FAILED':
        subject = f"❌ Glue Job Başarısız - {project_name}"
        message = f"""
Glue Job başarısız oldu!

📊 Job Detayları:
- Job Adı: {job_name}
- Durum: {state}
- Job Run ID: {job_run_id}
- Proje: {project_name}

Zaman: {event.get('time', 'Unknown')}

Lütfen CloudWatch loglarını kontrol edin.
"""
    else:
        subject = f"ℹ️ Glue Job Durumu - {project_name}"
        message = f"""
Glue Job durum değişikliği:

📊 Job Detayları:
- Job Adı: {job_name}
- Durum: {state}
- Job Run ID: {job_run_id}
- Proje: {project_name}

Zaman: {event.get('time', 'Unknown')}
"""
    
    # SNS'e gönder
    try:
        response = sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        print(f"Notification sent: {response['MessageId']}")
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        raise
    
    return {'statusCode': 200}