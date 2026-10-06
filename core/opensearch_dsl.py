import os
from botocore.auth import UNSIGNED_PAYLOAD
from opensearchpy import RequestsHttpConnection
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session
from urllib.parse import urlparse
from datetime import datetime
import pytz
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

import hashlib
import hmac

def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    k_date = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region_name)
    k_service = sign(k_region, service_name)
    k_signing = sign(k_service, 'aws4_request')
    return k_signing


class AOSSConnection(RequestsHttpConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.botocore_session = Session()
        self.region = os.getenv('AWS_REGION', 'us-east-2')

    def _sign_request(self, method, path, headers=None, body=None, params=None):
        """Sign the request using AWS SigV4 for OpenSearch Serverless"""
        # Construct the endpoint URL
        endpoint = f"{self.host}{path}"
        
        # Add query parameters if they exist
        if params:
            query_parts = []
            for k, v in params.items():
                if v is not None:
                    # Convert bytes to string if needed (for refresh parameter)
                    if isinstance(v, bytes):
                        v = v.decode('utf-8')
                    query_parts.append(f"{k}={v}")
            if query_parts:
                endpoint += f"?{'&'.join(query_parts)}"

        cleaned_headers = {k: v for k, v in (headers or {}).items() if v is not None}

        request = AWSRequest(
            method=method.upper(),
            url=endpoint,
            data=body,
            headers=cleaned_headers
        )

        # Set required headers
        parsed = urlparse(endpoint)
        request.headers['Host'] = parsed.hostname
        request.headers['x-amz-date'] = datetime.now(pytz.UTC).strftime('%Y%m%dT%H%M%SZ')

        # Get credentials
        credentials = self.botocore_session.get_credentials()
        if credentials is None:
            raise ValueError("❌ AWS credentials not found. Check your environment variables or AWS config.")

        # Prepare canonical components
        canonical_uri = parsed.path
        canonical_querystring = parsed.query if parsed.query else ''
        canonical_headers = f"host:{parsed.hostname}\nx-amz-date:{request.headers['x-amz-date']}\n"
        signed_headers = 'host;x-amz-date'
        
        if body is None:
            payload_hash = UNSIGNED_PAYLOAD
        elif isinstance(body, bytes):
            payload_hash = hashlib.sha256(body).hexdigest()
        else:
            payload_hash = hashlib.sha256(body.encode()).hexdigest()

        canonical_request = (
            f"{method.upper()}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )


        # Create string to sign
        algorithm = 'AWS4-HMAC-SHA256'
        amz_date = request.headers['x-amz-date']
        datestamp = amz_date[:8]
        credential_scope = f"{datestamp}/{self.region}/es/aws4_request"
        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )


        # Calculate signature
        frozen_creds = credentials.get_frozen_credentials()
        signing_key = get_signature_key(frozen_creds.secret_key, datestamp, self.region, 'es')
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # Add authentication
        SigV4Auth(credentials, 'es', self.region).add_auth(request)

        return dict(request.headers.items())

    def perform_request(self, method, url, params=None, body=None, headers=None, ignore=(), timeout=None):
        try:
            signed_headers = self._sign_request(
                method=method, 
                path=url,
                headers=headers,
                body=body,
                params=params
            )
            return super().perform_request(
                method=method,
                url=url,
                params=params,
                body=body,
                headers=signed_headers,
                ignore=ignore,
                timeout=timeout
            )
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
