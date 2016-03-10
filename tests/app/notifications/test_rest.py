from datetime import datetime
import uuid
import app.celery.tasks
from tests import create_authorization_header
from tests.app.conftest import sample_notification, sample_job, sample_service, sample_email_template, sample_template
from flask import json
from app.models import Service
from app.dao.templates_dao import dao_get_all_templates_for_service
from app.dao.services_dao import dao_update_service
from freezegun import freeze_time


def test_get_notification_by_id(notify_api, sample_notification):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            auth_header = create_authorization_header(
                service_id=sample_notification.service_id,
                path='/notifications/{}'.format(sample_notification.id),
                method='GET')

            response = client.get(
                '/notifications/{}'.format(sample_notification.id),
                headers=[auth_header])

            notification = json.loads(response.get_data(as_text=True))['notification']
            assert notification['status'] == 'sent'
            assert notification['template'] == sample_notification.template.id
            assert notification['to'] == '+447700900855'
            assert notification['service'] == str(sample_notification.service_id)
            assert response.status_code == 200


def test_get_notifications_empty_result(notify_api, sample_api_key):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            missing_notification_id = uuid.uuid4()
            auth_header = create_authorization_header(
                service_id=sample_api_key.service_id,
                path='/notifications/{}'.format(missing_notification_id),
                method='GET')

            response = client.get(
                path='/notifications/{}'.format(missing_notification_id),
                headers=[auth_header])

            notification = json.loads(response.get_data(as_text=True))
            assert notification['result'] == "error"
            assert notification['message'] == "not found"
            assert response.status_code == 404


def test_get_all_notifications(notify_api, sample_notification):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            auth_header = create_authorization_header(
                service_id=sample_notification.service_id,
                path='/notifications',
                method='GET')

            response = client.get(
                '/notifications',
                headers=[auth_header])

            notifications = json.loads(response.get_data(as_text=True))
            assert notifications['notifications'][0]['status'] == 'sent'
            assert notifications['notifications'][0]['template'] == sample_notification.template.id
            assert notifications['notifications'][0]['to'] == '+447700900855'
            assert notifications['notifications'][0]['service'] == str(sample_notification.service_id)
            assert response.status_code == 200


def test_get_all_notifications_newest_first(notify_api, notify_db, notify_db_session, sample_email_template):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            notification_1 = sample_notification(notify_db, notify_db_session, sample_email_template.service)
            notification_2 = sample_notification(notify_db, notify_db_session, sample_email_template.service)
            notification_3 = sample_notification(notify_db, notify_db_session, sample_email_template.service)

            auth_header = create_authorization_header(
                service_id=sample_email_template.service_id,
                path='/notifications',
                method='GET')

            response = client.get(
                '/notifications',
                headers=[auth_header])

            notifications = json.loads(response.get_data(as_text=True))
            assert len(notifications['notifications']) == 3
            assert notifications['notifications'][0]['to'] == notification_3.to
            assert notifications['notifications'][1]['to'] == notification_2.to
            assert notifications['notifications'][2]['to'] == notification_1.to
            assert response.status_code == 200


def test_get_all_notifications_for_service_in_order(notify_api, notify_db, notify_db_session):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            service_1 = sample_service(notify_db, notify_db_session, service_name="1")
            service_2 = sample_service(notify_db, notify_db_session, service_name="2")

            sample_notification(notify_db, notify_db_session, service=service_2)

            notification_1 = sample_notification(notify_db, notify_db_session, service=service_1)
            notification_2 = sample_notification(notify_db, notify_db_session, service=service_1)
            notification_3 = sample_notification(notify_db, notify_db_session, service=service_1)

            auth_header = create_authorization_header(
                path='/service/{}/notifications'.format(service_1.id),
                method='GET')

            response = client.get(
                path='/service/{}/notifications'.format(service_1.id),
                headers=[auth_header])

            resp = json.loads(response.get_data(as_text=True))
            assert len(resp['notifications']) == 3
            assert resp['notifications'][0]['to'] == notification_3.to
            assert resp['notifications'][1]['to'] == notification_2.to
            assert resp['notifications'][2]['to'] == notification_1.to
            assert response.status_code == 200


def test_get_all_notifications_for_job_in_order(notify_api, notify_db, notify_db_session, sample_service):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            main_job = sample_job(notify_db, notify_db_session, service=sample_service)
            another_job = sample_job(notify_db, notify_db_session, service=sample_service)

            notification_1 = sample_notification(
                notify_db, notify_db_session, job=main_job, to_field="1", created_at=datetime.utcnow()
            )
            notification_2 = sample_notification(
                notify_db, notify_db_session, job=main_job, to_field="2", created_at=datetime.utcnow()
            )
            notification_3 = sample_notification(
                notify_db, notify_db_session, job=main_job, to_field="3", created_at=datetime.utcnow()
            )
            sample_notification(notify_db, notify_db_session, job=another_job)

            auth_header = create_authorization_header(
                path='/service/{}/job/{}/notifications'.format(sample_service.id, main_job.id),
                method='GET')

            response = client.get(
                path='/service/{}/job/{}/notifications'.format(sample_service.id, main_job.id),
                headers=[auth_header])

            resp = json.loads(response.get_data(as_text=True))
            assert len(resp['notifications']) == 3
            assert resp['notifications'][0]['to'] == notification_3.to
            assert resp['notifications'][1]['to'] == notification_2.to
            assert resp['notifications'][2]['to'] == notification_1.to
            assert response.status_code == 200


def test_should_not_get_notifications_by_service_with_client_credentials(notify_api, sample_api_key):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            auth_header = create_authorization_header(
                service_id=sample_api_key.service.id,
                path='/service/{}/notifications'.format(sample_api_key.service.id),
                method='GET')

            response = client.get(
                '/service/{}/notifications'.format(sample_api_key.service.id),
                headers=[auth_header])

            resp = json.loads(response.get_data(as_text=True))
            assert response.status_code == 403
            assert resp['result'] == 'error'
            assert resp['message'] == 'Forbidden, invalid authentication token provided'


def test_should_not_get_notifications_by_job_and_service_with_client_credentials(notify_api, sample_job):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            auth_header = create_authorization_header(
                service_id=sample_job.service.id,
                path='/service/{}/job/{}/notifications'.format(sample_job.service.id, sample_job.id),
                method='GET')

            response = client.get(
                '/service/{}/job/{}/notifications'.format(sample_job.service.id, sample_job.id),
                headers=[auth_header])

            resp = json.loads(response.get_data(as_text=True))
            assert response.status_code == 403
            assert resp['result'] == 'error'
            assert resp['message'] == 'Forbidden, invalid authentication token provided'


def test_should_reject_invalid_page_param(notify_api, sample_email_template):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            auth_header = create_authorization_header(
                service_id=sample_email_template.service_id,
                path='/notifications',
                method='GET')

            response = client.get(
                '/notifications?page=invalid',
                headers=[auth_header])

            notifications = json.loads(response.get_data(as_text=True))
            assert response.status_code == 400
            assert notifications['result'] == 'error'
            assert notifications['message'] == 'Invalid page'


def test_should_return_pagination_links(notify_api, notify_db, notify_db_session, sample_email_template):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            notify_api.config['PAGE_SIZE'] = 1

            sample_notification(notify_db, notify_db_session, sample_email_template.service)
            notification_2 = sample_notification(notify_db, notify_db_session, sample_email_template.service)
            sample_notification(notify_db, notify_db_session, sample_email_template.service)

            auth_header = create_authorization_header(
                service_id=sample_email_template.service_id,
                path='/notifications',
                method='GET')

            response = client.get(
                '/notifications?page=2',
                headers=[auth_header])

            notifications = json.loads(response.get_data(as_text=True))
            assert len(notifications['notifications']) == 1
            assert notifications['links']['last'] == '/notifications?page=3'
            assert notifications['links']['prev'] == '/notifications?page=1'
            assert notifications['links']['next'] == '/notifications?page=3'
            assert notifications['notifications'][0]['to'] == notification_2.to
            assert response.status_code == 200


def test_get_all_notifications_returns_empty_list(notify_api, sample_api_key):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            auth_header = create_authorization_header(
                service_id=sample_api_key.service.id,
                path='/notifications',
                method='GET')

            response = client.get(
                '/notifications',
                headers=[auth_header])

            notifications = json.loads(response.get_data(as_text=True))
            assert response.status_code == 200
            assert len(notifications['notifications']) == 0


def test_create_sms_should_reject_if_missing_required_fields(notify_api, sample_api_key, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')

            data = {}
            auth_header = create_authorization_header(
                service_id=sample_api_key.service_id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_sms.apply_async.assert_not_called()
            assert json_resp['result'] == 'error'
            assert 'Missing data for required field.' in json_resp['message']['to'][0]
            assert 'Missing data for required field.' in json_resp['message']['template'][0]
            assert response.status_code == 400


def test_should_reject_bad_phone_numbers(notify_api, sample_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')

            data = {
                'to': 'invalid',
                'template': sample_template.id
            }
            auth_header = create_authorization_header(
                service_id=sample_template.service.id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_sms.apply_async.assert_not_called()
            assert json_resp['result'] == 'error'
            assert len(json_resp['message'].keys()) == 1
            assert 'Invalid phone number: Must not contain letters or symbols' in json_resp['message']['to']
            assert response.status_code == 400


def test_send_notification_invalid_template_id(notify_api, sample_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')

            data = {
                'to': '+447700900855',
                'template': 9999
            }
            auth_header = create_authorization_header(
                service_id=sample_template.service.id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_sms.apply_async.assert_not_called()

            assert response.status_code == 404
            assert len(json_resp['message'].keys()) == 1
            test_string = 'Template {} not found for service {}'.format(9999, sample_template.service.id)
            assert test_string in json_resp['message']['template']


@freeze_time("2016-01-01 11:09:00.061258")
def test_send_notification_with_placeholders_replaced(notify_api, sample_template_with_placeholders, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')
            mocker.patch('app.encryption.encrypt', return_value="something_encrypted")

            data = {
                'to': '+447700900855',
                'template': sample_template_with_placeholders.id,
                'personalisation': {
                    'name': 'Jo'
                }
            }
            auth_header = create_authorization_header(
                service_id=sample_template_with_placeholders.service.id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            notification_id = json.loads(response.data)['notification_id']
            app.celery.tasks.send_sms.apply_async.assert_called_once_with(
                (str(sample_template_with_placeholders.service.id),
                 notification_id,
                 "something_encrypted",
                 "2016-01-01T11:09:00.061258"),
                queue="sms"
            )
            assert response.status_code == 201


def test_send_notification_with_missing_personalisation(notify_api, sample_template_with_placeholders, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')

            data = {
                'to': '+447700900855',
                'template': sample_template_with_placeholders.id,
                'personalisation': {
                    'foo': 'bar'
                }
            }
            auth_header = create_authorization_header(
                service_id=sample_template_with_placeholders.service.id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_sms.apply_async.assert_not_called()

            assert response.status_code == 400
            assert 'Missing personalisation: name' in json_resp['message']['template']


def test_send_notification_with_too_much_personalisation_data(
        notify_api, sample_template_with_placeholders, mocker
):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')

            data = {
                'to': '+447700900855',
                'template': sample_template_with_placeholders.id,
                'personalisation': {
                    'name': 'Jo', 'foo': 'bar'
                }
            }
            auth_header = create_authorization_header(
                service_id=sample_template_with_placeholders.service.id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_sms.apply_async.assert_not_called()

            assert response.status_code == 400
            assert 'Personalisation not needed for template: foo' in json_resp['message']['template']


def test_prevents_sending_to_any_mobile_on_restricted_service(notify_api, sample_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')

            Service.query.filter_by(
                id=sample_template.service.id
            ).update(
                {'restricted': True}
            )
            invalid_mob = '+447700900855'
            data = {
                'to': invalid_mob,
                'template': sample_template.id
            }

            auth_header = create_authorization_header(
                service_id=sample_template.service.id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_sms.apply_async.assert_not_called()

            assert response.status_code == 400
            assert 'Invalid phone number for restricted service' in json_resp['message']['to']


def test_should_not_allow_template_from_another_service(notify_api, service_factory, sample_user, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')

            service_1 = service_factory.get('service 1', user=sample_user)
            service_2 = service_factory.get('service 2', user=sample_user)

            service_2_templates = dao_get_all_templates_for_service(service_id=service_2.id)
            data = {
                'to': sample_user.mobile_number,
                'template': service_2_templates[0].id
            }

            auth_header = create_authorization_header(
                service_id=service_1.id,
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST')

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_sms.apply_async.assert_not_called()

            assert response.status_code == 404
            test_string = 'Template {} not found for service {}'.format(service_2_templates[0].id, service_1.id)
            assert test_string in json_resp['message']['template']


@freeze_time("2016-01-01 11:09:00.061258")
def test_should_allow_valid_sms_notification(notify_api, sample_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')
            mocker.patch('app.encryption.encrypt', return_value="something_encrypted")

            data = {
                'to': '07700 900 855',
                'template': sample_template.id
            }

            auth_header = create_authorization_header(
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST',
                service_id=sample_template.service_id
            )

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            notification_id = json.loads(response.data)['notification_id']
            assert app.encryption.encrypt.call_args[0][0]['to'] == '+447700900855'
            app.celery.tasks.send_sms.apply_async.assert_called_once_with(
                (str(sample_template.service_id),
                 notification_id,
                 "something_encrypted",
                 "2016-01-01T11:09:00.061258"),
                queue="sms"
            )
            assert response.status_code == 201
            assert notification_id


def test_create_email_should_reject_if_missing_required_fields(notify_api, sample_api_key, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')

            data = {}
            auth_header = create_authorization_header(
                service_id=sample_api_key.service_id,
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST')

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_email.apply_async.assert_not_called()
            assert json_resp['result'] == 'error'
            assert 'Missing data for required field.' in json_resp['message']['to'][0]
            assert 'Missing data for required field.' in json_resp['message']['template'][0]
            assert response.status_code == 400


def test_should_reject_email_notification_with_bad_email(notify_api, sample_email_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')
            to_address = "bad-email"
            data = {
                'to': to_address,
                'template': sample_email_template.service.id
            }
            auth_header = create_authorization_header(
                service_id=sample_email_template.service.id,
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST')

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            data = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_email.apply_async.assert_not_called()
            assert response.status_code == 400
            assert data['result'] == 'error'
            assert data['message']['to'][0] == 'Not a valid email address'


def test_should_reject_email_notification_with_template_id_that_cant_be_found(
        notify_api, sample_email_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')
            data = {
                'to': 'ok@ok.com',
                'template': 1234
            }
            auth_header = create_authorization_header(
                service_id=sample_email_template.service.id,
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST')

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            data = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_email.apply_async.assert_not_called()
            assert response.status_code == 404
            assert data['result'] == 'error'
            test_string = 'Template {} not found for service {}'.format(
                1234,
                sample_email_template.service.id
            )
            assert test_string in data['message']['template']


def test_should_not_allow_email_template_from_another_service(notify_api, service_factory, sample_user, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')

            service_1 = service_factory.get('service 1', template_type='email', user=sample_user)
            service_2 = service_factory.get('service 2', template_type='email', user=sample_user)

            service_2_templates = dao_get_all_templates_for_service(service_id=service_2.id)

            data = {
                'to': sample_user.email_address,
                'template': service_2_templates[0].id
            }

            auth_header = create_authorization_header(
                service_id=service_1.id,
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST')

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_email.apply_async.assert_not_called()

            assert response.status_code == 404
            test_string = 'Template {} not found for service {}'.format(service_2_templates[0].id, service_1.id)
            assert test_string in json_resp['message']['template']


def test_should_not_send_email_if_restricted_and_not_a_service_user(notify_api, sample_email_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')

            sample_email_template.service.restricted = True
            dao_update_service(sample_email_template)

            data = {
                'to': "not-someone-we-trust@email-address.com",
                'template': sample_email_template.id
            }

            auth_header = create_authorization_header(
                service_id=sample_email_template.service.id,
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST')

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_email.apply_async.assert_not_called()

            assert response.status_code == 400
            assert 'Email address not permitted for restricted service' in json_resp['message']['to']


def test_should_not_send_email_for_job_if_restricted_and_not_a_service_user(
        notify_api,
        sample_job,
        sample_email_template,
        mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')

            sample_email_template.service.restricted = True
            dao_update_service(sample_email_template)

            data = {
                'to': "not-someone-we-trust@email-address.com",
                'template': sample_job.template.id,
                'job': sample_job.id
            }

            auth_header = create_authorization_header(
                service_id=sample_job.service.id,
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST')

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            json_resp = json.loads(response.get_data(as_text=True))
            app.celery.tasks.send_email.apply_async.assert_not_called()

            assert response.status_code == 400
            assert 'Email address not permitted for restricted service' in json_resp['message']['to']


@freeze_time("2016-01-01 11:09:00.061258")
def test_should_allow_valid_email_notification(notify_api, sample_email_template, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')
            mocker.patch('app.encryption.encrypt', return_value="something_encrypted")

            data = {
                'to': 'ok@ok.com',
                'template': sample_email_template.id
            }

            auth_header = create_authorization_header(
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST',
                service_id=sample_email_template.service_id
            )

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])
            assert response.status_code == 201
            notification_id = json.loads(response.get_data(as_text=True))['notification_id']
            app.celery.tasks.send_email.apply_async.assert_called_once_with(
                (str(sample_email_template.service_id),
                 notification_id,
                 "Email Subject",
                 "sample.service@test.notify.com",
                 "something_encrypted",
                 "2016-01-01T11:09:00.061258"),
                queue="email"
            )
            assert response.status_code == 201
            assert notification_id


@freeze_time("2016-01-01 12:00:00.061258")
def test_should_block_api_call_if_over_day_limit(notify_db, notify_db_session, notify_api, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_email.apply_async')
            mocker.patch('app.encryption.encrypt', return_value="something_encrypted")

            service = sample_service(notify_db, notify_db_session, limit=1)
            email_template = sample_email_template(notify_db, notify_db_session, service=service)
            sample_notification(
                notify_db, notify_db_session, template=email_template, service=service, created_at=datetime.utcnow()
            )

            data = {
                'to': 'ok@ok.com',
                'template': email_template.id
            }

            auth_header = create_authorization_header(
                request_body=json.dumps(data),
                path='/notifications/email',
                method='POST',
                service_id=service.id
            )

            response = client.post(
                path='/notifications/email',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])
            json_resp = json.loads(response.get_data(as_text=True))

            assert response.status_code == 429
            assert 'Exceeded send limits (1) for today' in json_resp['message']


@freeze_time("2016-01-01 12:00:00.061258")
def test_should_block_api_call_if_over_day_limit_regardless_of_type(notify_db, notify_db_session, notify_api, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')
            mocker.patch('app.encryption.encrypt', return_value="something_encrypted")

            service = sample_service(notify_db, notify_db_session, limit=1)
            email_template = sample_email_template(notify_db, notify_db_session, service=service)
            sms_template = sample_template(notify_db, notify_db_session, service=service)
            sample_notification(
                notify_db, notify_db_session, template=email_template, service=service, created_at=datetime.utcnow()
            )

            data = {
                'to': '+447234123123',
                'template': sms_template.id
            }

            auth_header = create_authorization_header(
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST',
                service_id=service.id
            )

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])
            json_resp = json.loads(response.get_data(as_text=True))
            assert response.status_code == 429
            assert 'Exceeded send limits (1) for today' in json_resp['message']


@freeze_time("2016-01-01 12:00:00.061258")
def test_should_allow_api_call_if_under_day_limit_regardless_of_type(notify_db, notify_db_session, notify_api, mocker):
    with notify_api.test_request_context():
        with notify_api.test_client() as client:
            mocker.patch('app.celery.tasks.send_sms.apply_async')
            mocker.patch('app.encryption.encrypt', return_value="something_encrypted")

            service = sample_service(notify_db, notify_db_session, limit=2)
            email_template = sample_email_template(notify_db, notify_db_session, service=service)
            sms_template = sample_template(notify_db, notify_db_session, service=service)
            sample_notification(notify_db, notify_db_session, template=email_template, service=service)

            data = {
                'to': '+447634123123',
                'template': sms_template.id
            }

            auth_header = create_authorization_header(
                request_body=json.dumps(data),
                path='/notifications/sms',
                method='POST',
                service_id=service.id
            )

            response = client.post(
                path='/notifications/sms',
                data=json.dumps(data),
                headers=[('Content-Type', 'application/json'), auth_header])

            assert response.status_code == 201
