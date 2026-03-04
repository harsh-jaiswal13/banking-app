Python Internals
GIL, CPython internals & memory model
Dunder methods, descriptors, metaclasses
Decorators, context managers, generators
Type hints, dataclasses, Protocol
Slots, weakrefs, object lifecycle


Data Structures & Algorithms
Big-O analysis, time & space complexity
Hash maps, heaps, trees, graphs
Sorting, searching, dynamic programming
Python collections module deeply

Concurrency Basics
Threading vs multiprocessing vs asyncio
Event loop fundamentals
async/await, coroutines, tasks
concurrent.futures, ProcessPoolExecutor


Testing Fundamentals
pytest, fixtures, parametrize
Mocking with unittest.mock
TDD methodology
Coverage reports, mutation testing
Tier 02

FastAPI / Django / Flask
FastAPI: Pydantic v2, dependency injection
Middleware stack, request lifecycle
Background tasks, WebSockets, SSE
Django ORM, signals, custom managers
WSGI vs ASGI servers (Gunicorn, Uvicorn)

REST & API Design
RESTful principles, HTTP semantics
Versioning strategies
OpenAPI spec, auto-generated docs
Rate limiting, pagination patterns
Idempotency keys, retry logic

Databases: SQL
PostgreSQL: indexing, EXPLAIN ANALYZE
SQLAlchemy ORM + Core, Alembic migrations
Transactions, ACID, isolation levels
N+1 problem, query optimization
Connection pooling (PgBouncer)

Caching & Redis
Redis data structures & use cases
Cache-aside, write-through patterns
TTL strategy, cache invalidation
Redis Pub/Sub, Streams
Celery task queues with Redis broker

Architecture Patterns
Microservices vs monolith tradeoffs
Event-driven architecture, CQRS, Event Sourcing
Hexagonal / Clean Architecture in Python
Domain-Driven Design (DDD) basics
Strangler fig, saga patterns

Messaging & Queues
Kafka: producers, consumers, partitions, offsets
RabbitMQ: exchanges, routing keys, DLX
At-least-once vs exactly-once delivery
Outbox pattern for reliable events
Celery beat, chords, chains

Distributed Systems
CAP theorem, consistency models
Service discovery, load balancing
Circuit breakers, bulkheads (Resilience)
Distributed tracing (OpenTelemetry)
Leader election, consensus basics

Security
OAuth2, OIDC, JWT best practices
OWASP Top 10, SQL injection, XSS
Secrets management (Vault, AWS Secrets)
Rate limiting, CORS, CSRF tokens
mTLS between services

NoSQL & Search
MongoDB: aggregation pipeline, indexes
Elasticsearch / OpenSearch full-text search
DynamoDB access patterns
Time-series DBs (InfluxDB, TimescaleDB)

API Gateway & gRPC
gRPC with protobuf, streaming RPCs
GraphQL with Strawberry/Ariadne
API gateway patterns (Kong, AWS API GW)
Service mesh basics (Istio, Envoy)

Observability
Structured logging (structlog, JSON logs)
Prometheus + Grafana dashboards
Distributed tracing with Jaeger/Tempo
SLO/SLA/SLI definitions
Alerting, PagerDuty runbooks

/CD Pipelines
GitHub Actions, GitLab CI workflows
Blue-green & canary deployments
Feature flags (LaunchDarkly)
Rollback strategies
GitOps with ArgoCD/Flux

Containers & Kubernetes
Docker: multi-stage builds, layer caching
Kubernetes: Deployments, Services, Ingress
HPA, resource limits, liveness probes
Helm charts, Kustomize
Namespace isolation, RBAC

Cloud (AWS / GCP)
EC2, ECS Fargate, Lambda, EKS
RDS, ElastiCache, S3, SQS, SNS
IAM roles, VPC, security groups
CDK / Terraform for IaC
Cost optimization, reserved instances


⚡
Performance Engineering
Profiling with cProfile, py-spy, memray
Async optimization, uvloop, httpx
Database query plan analysis
Caching layers strategy (L1/L2/L3)
Load testing with Locust, k6
🛡️
Resilience Patterns
Circuit breakers (tenacity, pybreaker)
Retry with exponential backoff + jitter
Graceful degradation, fallbacks
Chaos engineering basics
Database failover, replica routing
📐
Advanced Data Patterns
Read replicas, write sharding
Multi-region data replication
Data pipelines (Airflow, Prefect)
CDC with Debezium
Lake house architecture
🔬
Engineering Leadership
RFC / ADR (Architecture Decision Records)
Code review culture, PR standards
Technical debt triage
On-call, incident management (SRE basics)
Capacity planning

LLM APIs & SDKs
OpenAI / Anthropic SDK usage
Streaming responses (SSE)
Token counting, cost management
Function calling / tool use
Structured output parsing
RAG Systems
Vector databases (pgvector, Qdrant, Pinecone)
Embedding models & chunking strategies
Hybrid search (BM25 + semantic)
Context window management
Reranking with Cohere / Cross-encoders
Agent Frameworks
LangChain / LangGraph orchestration
Tool-calling agent loops
Memory: episodic, semantic, working
Multi-agent coordination patterns
Human-in-the-loop checkpoints
ML Engineering
Model serving: vLLM, Triton, BentoML
Fine-tuning: LoRA, QLoRA, PEFT
Quantization (GGUF, AWQ, GPTQ)
Batch inference pipelines
A/B testing model versions
Prompt Engineering
System prompt design patterns
Chain-of-thought, ReAct, Self-consistency
Prompt injection defense
Eval frameworks (RAGAS, DeepEval)
Few-shot example selection
AI Infra & Observability
LLM observability (LangSmith, Langfuse)
Token budgeting & quota management
Guardrails & content filtering
Caching LLM responses (semantic cache)
Async batch processing for AI tasks