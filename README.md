# Finde

Finde is a secondhand fashion discovery marketplace that I designed and built end-to-end. The application combines product design, full-stack engineering, marketplace APIs, search infrastructure, and AI-assisted computer vision to make secondhand clothing easier to discover.

Finde pulls live inventory from the eBay API, normalizes listing and sizing data, processes garment images to identify fashion attributes, and indexes listings in OpenSearch for fast search and filtering.

**Public repository notice:** This is a public, sanitized copy of a private production repository. Credentials, internal infrastructure details, and proprietary production algorithms have been removed or replaced with simplified implementations so the code can be shared safely. This repository is intended to demonstrate the application's architecture and engineering approach; some production functionality depends on external services, credentials, and proprietary components that are not included here.

## My Role

I designed and built Finde from concept through production as a solo product and engineering project.

My work includes:

- Product strategy and UX/UI design
- Django application architecture and backend development
- Database and data-model design
- REST API development
- eBay marketplace API integration and OAuth
- Listing ingestion, normalization, and lifecycle management
- OpenSearch indexing and search infrastructure
- Clothing and shoe size parsing across US, EU, UK, JP, and KR sizing systems
- Computer-vision and AI-assisted garment classification
- AWS S3 media storage
- Redis caching and rate limiting
- Authentication and account functionality
- Responsive frontend implementation
- Docker-based local development
- Production deployment and infrastructure

## Product

Finde is designed around the idea that secondhand marketplaces contain enormous amounts of inventory, but finding something specific can be difficult.

The product focuses on making discovery feel more like a curated shopping experience, with visual browsing, size-aware filtering, saved items, and fashion-specific search and categorization.

Product case study: https://anneleedesigns.com/finde

The case study documents the product strategy, UX decisions, marketplace architecture, search and filtering system, research, and end-to-end build.

## Stack

- **Backend:** Django, Django REST Framework, django-allauth
- **Database:** MySQL via mysqlclient / PyMySQL
- **Search:** OpenSearch via django-opensearch-dsl, including AWS SigV4-signed connections for managed OpenSearch
- **Caching / rate limiting:** Redis, django-ratelimit
- **Storage:** AWS S3 via django-storages and boto3
- **Computer vision:** PyTorch, transformers (YOLOS object detection), OpenCV, scikit-learn (K-means color clustering), Pillow — optional, see `requirements-ml.txt`
- **AI:** Anthropic Claude Vision API for fashion-item classification
- **Marketplace integration:** eBay Trading/Browse APIs with OAuth2 and sandbox/production environments
- **Deployment:** Docker / docker-compose, Railway
- **CI:** GitHub Actions (system check + test suite on every push)

## Architecture Overview

```
                         eBay APIs
                            │
                            ▼
                  Listing ingestion / sync
                            │
                            ▼
                     Django / Python
                      ╱           ╲
                     ▼             ▼
                  MySQL        OpenSearch
                                   │
                                   ▼
                            Search / filtering
                                   │
                                   ▼
                              Finde UI


User garment image
        │
        ▼
Computer vision / Claude
        │
        ▼
Category · color · material
        │
        ▼
Listing data / search index
```

## Application structure

```
finde/
    Django project configuration
    settings, URLs, WSGI/ASGI

    ebay_search.py
        eBay OAuth token caching and API request helpers

    find_relistedItemId.py
        Item availability and relisting logic

core/
    models.py
        Listing, user, and size-conversion models

    views/
        Web views and API endpoints, split by feature area:
        pages, accounts, favorites, search (OpenSearch query
        building and browse), ebay_import (admin ingestion tools),
        marketplace (listing creation APIs), uploads

    documents.py
        OpenSearch index definitions

    opensearch_dsl.py
        AWS-signed OpenSearch connection class

    size_sorting.py
    size_shoe_sorting.py
        Size parsing and normalization

    fashion_taxonomy.py
    maps_and_terms.py
    curated_filters.py
        Category and merchandising configuration

    listings/
        smart_fashion_detection.py
            Computer-vision garment detection

        claude_fashion_detection.py
            Claude Vision-based classification

    management/commands/
        OpenSearch synchronization
        Listing lifecycle management

    tests/
        Access control, forms, API, template filter and
        image-processing tests; size-parser tests run when the
        production parser is present
```

## Key Engineering Areas

### Marketplace Integration

Finde integrates with eBay APIs to retrieve marketplace inventory and maintain listing availability.

The application handles authentication, API requests, listing normalization, and inventory lifecycle events while translating third-party marketplace data into Finde's internal data model.

### Search and Filtering

Listing data is indexed in OpenSearch to support fast browsing and fashion-specific filtering.

This separates search-oriented indexing from the application's relational data model and allows the browsing experience to work with a large volume of marketplace inventory.

### Size Normalization

Clothing and shoe listings frequently contain inconsistent sizing information.

Finde includes custom parsing and normalization logic for clothing and footwear across multiple regional sizing systems, including US, EU, UK, JP, and KR sizing.

The production implementation of these rules is proprietary and has been replaced with simplified implementations in this public repository.

### Computer Vision and AI

Garment images can be processed through a computer-vision pipeline to identify fashion attributes such as item category, color, and material.

The system combines object detection, image processing, clustering, and AI-assisted classification using PyTorch, YOLOS, OpenCV, and Claude Vision.

The production detection and classification heuristics are proprietary and are not included in this public repository.

### Security

- Catalog-management endpoints (eBay import, item curation, deletion, availability sync) are restricted to the admin account through a shared `admin_required` decorator.
- Login, signup and account endpoints are rate limited, and signup is protected by reCAPTCHA.
- Image-upload endpoints require POST and CSRF tokens.
- Data passed from Django to JavaScript uses `json_script`, so listing titles from eBay can't break out of a script tag.

### Media and Infrastructure

User and listing media are stored using AWS S3. The application is containerized with Docker and deployed through Railway.

## Running Locally

### Prerequisites

- Python 3.11
- MySQL
- OpenSearch
- Redis (cache and rate limiting)

### Setup

```bash
cp .env.example .env

# Fill in .env with your own values:
# database, email, AWS, eBay, Anthropic, etc.

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
# Optional: on-device garment detection (PyTorch, transformers, OpenCV)
pip install -r requirements-ml.txt

python manage.py migrate
python manage.py runserver
```

### With Docker

```bash
cp .env.example .env
docker-compose up --build
```

This starts Django, MySQL, OpenSearch and Redis. Inside Docker the app talks to a plain local OpenSearch node (`OPENSEARCH_USE_AWS=False`); in production it signs requests for AWS-managed OpenSearch.

### Running the Tests

```bash
python manage.py test --settings=finde.settings_test
```

The test settings swap MySQL, Redis, S3 and SMTP for in-process equivalents, so no credentials or services are needed. The same command runs in GitHub Actions on every push.

### Local Development Notes

- `EBAY_ENV` controls sandbox vs. production eBay credentials. Use sandbox for local development.
- OpenSearch indices can be initialized with:

```bash
python manage.py opensearch_init
```

- OpenSearch synchronization is handled through the `sync_opensearch_*` management commands.
- Set `LOG_LEVEL=DEBUG` to see size-parsing and search diagnostics.
- The eBay and Anthropic integrations require their respective API credentials and external services.

The public repository does not reproduce every production feature without the corresponding external services, credentials, and proprietary components.

## Proprietary Components

Several components in the private production repository contain proprietary business logic. In this public repository their function bodies are replaced with stubs that keep the original interfaces, signatures and docstrings.

`claude_fashion_detection.py` is the exception: it is a working implementation with a simplified prompt in place of the production one.

These include:

- `core/listings/smart_fashion_detection.py`
- `core/listings/claude_fashion_detection.py`
- `core/size_sorting.py`
- `core/size_shoe_sorting.py`
- `core/fashion_taxonomy.py`
- `core/maps_and_terms.py`
- `core/curated_filters.py`
- `finde/ebay_search.py`
- `finde/find_relistedItemId.py`

The omitted production logic includes proprietary detection heuristics, size-matching rules, merchandising and category curation, ranking logic, and marketplace synchronization behavior.

The remaining application code demonstrates the surrounding application architecture, including Django models and views, authentication, templates, API integrations, OpenSearch integration, and application-level data flow.

Tests for the stubbed size parser are kept in the repository and are skipped automatically while the parser is stubbed.

## What I'd Improve Next

Finde grew feature by feature as a solo project, and some parts reflect that. If I were continuing it with a team, these are the changes I'd make first:

- **Break up the largest functions.** The eBay import view (`save_selected_items`, about 1,300 lines) and the search view (`opensearch_results`, about 900 lines) each do several jobs. I'd pull them into an ingestion pipeline and a query-builder module, each with focused unit tests.
- **Move ingestion off the request path.** Importing listings and converting images happens inside the admin's web request. A task queue would make imports resumable and keep the admin UI responsive.
- **Modularize the frontend.** The listing-creation template and `browse.js` each hold thousands of lines of inline JavaScript. I'd split them into modules with a small build step.
- **Use Django's permission system.** Admin access currently checks a single configured username. Staff flags or groups would support more than one curator.
- **Test against real services in CI.** The suite runs without external services. Adding OpenSearch and MySQL service containers would let integration tests cover search and indexing end to end.

## Product Case Study

The complete product and design case study is available at:

https://anneleedesigns.com/finde

It covers the product strategy, user research, design system, discovery experience, filtering architecture, marketplace strategy, and technical approach behind Finde.

## About the Project

Finde was built independently from concept through production, combining product design with full-stack engineering.

The public repository is intentionally curated to make the architecture, implementation patterns, and engineering decisions inspectable while protecting proprietary production logic.
