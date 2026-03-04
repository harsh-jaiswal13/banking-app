BACKEND ENGINEER – LEARNING PATH (Basic → Advanced)
Arranged so each section builds on the previous one.
══════
STAGE 2 – BACKEND CORE
(Build your first real APIs)
═══════════════════════════════════════════════════════

--- Python Intermediate ---
- Decorators: writing your own with functools.wraps
- Dataclasses and Pydantic basics for data modeling
- Type hints: str, int, list, dict, Optional, Union
- Abstract base classes (abc module)
- __slots__, __repr__, __eq__, __hash__
- Exception hierarchy: custom exception classes
- Logging module: levels, handlers, formatters
- os, pathlib, shutil for file operations
- datetime, timezone handling (use UTC always)
- Regular expressions basics (re module)

--- FastAPI Fundamentals ---
- Project setup and folder structure
- Path parameters and query parameters
- Request body with Pydantic models
- Response models and status codes
- Path operations: GET, POST, PUT, PATCH, DELETE
- Dependency injection basics
- Routers for organizing endpoints
- Error handling: HTTPException, custom exception handlers
- OpenAPI docs: automatic Swagger UI
- Middleware basics: logging, timing requests
- CORS middleware setup
- Running with uvicorn

--- API Design Basics ---
- RESTful resource naming: nouns not verbs
- Consistent response envelope: {data, error, meta}
- Pagination: offset-based first, then cursor-based
- Filtering and sorting via query params
- API versioning: /v1/, /v2/
- HTTP 422 for validation errors vs 400 for bad requests
- Idempotency: understanding the concept
- Request validation and sanitization

--- SQL & Relational Databases ---
- Tables, rows, columns, data types
- Primary keys, foreign keys, constraints
- CRUD: INSERT, SELECT, UPDATE, DELETE
- Joins: INNER, LEFT, RIGHT, FULL
- WHERE, ORDER BY, GROUP BY, HAVING
- Indexes: what they are and why they matter
- Transactions: BEGIN, COMMIT, ROLLBACK
- ACID properties
- Basic normalization: 1NF, 2NF, 3NF
- PostgreSQL setup and psql CLI basics
- SQLAlchemy: models, sessions, queries (ORM basics)
- Alembic: creating and running migrations

═══════════════════════════════════════════════════════
STAGE 3 – PRODUCTION READINESS
(Make your code deployable and maintainable)
═══════════════════════════════════════════════════════

--- Testing ---
- pytest: fixtures, parametrize, marks
- Unit tests: testing functions in isolation
- Integration tests: testing with a real DB
- FastAPI TestClient for endpoint testing
- Mocking: unittest.mock, pytest-mock
- Test coverage: coverage.py
- Factory pattern for test data (factory_boy)
- Testing error cases, not just happy paths
- What NOT to test (implementation details)

--- Docker Basics ---
- What containers are and why they matter
- Writing a Dockerfile: FROM, COPY, RUN, CMD, EXPOSE
- .dockerignore
- Building and running images
- Environment variables in containers
- Docker Compose: defining multi-service apps
- Volumes and bind mounts
- Docker networking: how containers talk to each other
- Non-root user in containers (security)
- Multi-stage builds to reduce image size

--- Authentication & Authorization Basics ---
- Password hashing: bcrypt, argon2 – never store plaintext
- JWT: structure (header.payload.signature), signing, expiry
- Access token vs refresh token pattern
- OAuth 2.0 concepts: flows, scopes, tokens
- FastAPI security utilities: OAuth2PasswordBearer
- API key authentication
- Basic RBAC: roles attached to users, permission checks
- Storing secrets: environment variables, never in code

--- Structured Logging & Basic Observability ---
- Why structured (JSON) logging matters
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Adding context: request_id, user_id to every log line
- Avoiding logging sensitive data (passwords, tokens, PII)
- Health check endpoint: /health, /ready
- Basic metrics: request count, error rate, latency
- Reading application logs in production

--- Environment & Config Management ---
- 12-factor app principles
- pydantic-settings for config management
- .env files and python-dotenv
- Separating config per environment: dev, staging, prod
- Never hardcode secrets or URLs
- Feature flags: basic boolean flags in config

═══════════════════════════════════════════════════════
STAGE 4 – DATABASES IN DEPTH
(Go beyond basic CRUD)
═══════════════════════════════════════════════════════

--- SQL Advanced ---
- Query execution plans: EXPLAIN ANALYZE
- Index types: B-tree (default), Hash, GIN (JSONB/arrays), BRIN (time-series)
- Composite indexes and column order
- Covering indexes (index-only scans)
- Partial indexes and expression indexes
- Transaction isolation levels: Read Committed, Repeatable Read, Serializable
- MVCC in PostgreSQL: how it handles concurrent reads/writes
- Row-level locking: SELECT FOR UPDATE, SKIP LOCKED
- Deadlock: how it happens, how to avoid it
- Window functions: ROW_NUMBER, RANK, LAG, LEAD, PARTITION BY
- CTEs: WITH clause, recursive CTEs
- LATERAL joins
- Materialized views and when to use them
- Table partitioning: range, list, hash
- pg_stat_statements: finding slow queries
- Zero-downtime migrations: expand-contract pattern
- Optimistic locking with version columns

--- Connection Pooling ---
- Why direct DB connections don't scale
- PgBouncer: session vs transaction vs statement mode
- SQLAlchemy connection pool settings: pool_size, max_overflow
- Connection limits in PostgreSQL (max_connections)
- Monitoring pool exhaustion

--- Redis ---
- Data structures: strings, hashes, lists, sets, sorted sets
- TTL and expiry
- Redis as cache: cache-aside pattern
- Redis as session store
- Pub/Sub basics
- Streams for simple message passing
- HyperLogLog for approximate cardinality
- Bloom filters for membership testing
- Persistence: RDB snapshots vs AOF
- Redis Sentinel vs Redis Cluster
- Atomic operations with MULTI/EXEC pipeline

--- NoSQL Basics ---
- MongoDB: documents, collections, BSON
- MongoDB CRUD and aggregation pipeline
- Indexing in MongoDB
- When to choose MongoDB over PostgreSQL
- DynamoDB basics: partition key, sort key, GSI
- Single-table design concept in DynamoDB
- Key-value stores: use cases

═══════════════════════════════════════════════════════
STAGE 5 – ASYNC, QUEUES & BACKGROUND PROCESSING
(Handle work that takes time)
═══════════════════════════════════════════════════════

--- Async Python ---
- async/await syntax
- Event loop: what it is, how it works
- asyncio.gather: running tasks concurrently
- asyncio.Queue for producer-consumer within a process
- asyncio.Semaphore: limiting concurrent operations
- asyncio.Lock for shared state
- asyncio.timeout and cancellation
- run_in_executor: offloading blocking code
- Detecting blocking code in async context
- uvloop as performance upgrade
- aiohttp and httpx for async HTTP
- Async SQLAlchemy: async sessions and queries

--- Streaming Responses ---
- Server-Sent Events (SSE): how they work
- WebSockets: handshake, frames, close
- StreamingResponse in FastAPI
- Long polling: when to use it
- Chunked transfer encoding
- Backpressure: what happens when client is slow

--- Task Queues with Celery ---
- What Celery is and when you need it
- Celery with Redis or RabbitMQ as broker
- Defining tasks with @app.task
- Calling tasks: .delay() and .apply_async()
- Task retries: max_retries, countdown, exponential backoff
- Task routing to specific queues
- Chains, groups, chords for task composition
- Celery beat for scheduled (cron-like) tasks
- Task result backends
- Monitoring with Flower
- Making tasks idempotent (same result if run twice)

--- Message Queues ---
- Why message queues exist: decoupling producers from consumers
- RabbitMQ: exchanges, queues, bindings
- Exchange types: direct, fanout, topic, headers
- Message acknowledgements: ack, nack, reject
- Dead letter exchanges (DLX) for failed messages
- Prefetch count (QoS) for consumer throughput
- Publisher confirms for reliability
- Kafka: topics, partitions, consumer groups
- Kafka offset management: auto vs manual commit
- Kafka producer: acks, retries, idempotent producer
- Outbox pattern: publishing events reliably from DB transactions

═══════════════════════════════════════════════════════
STAGE 6 – SCALABILITY & PERFORMANCE
(Make things fast under load)
═══════════════════════════════════════════════════════

--- Caching Deep Dive ---
- Cache-aside (lazy loading) – most common pattern
- Write-through caching
- Write-behind (write-back) caching
- Read-through caching
- Cache invalidation strategies: TTL, event-driven, versioned keys
- Cache stampede / thundering herd problem and solutions
- Negative caching: caching 404 / empty results
- Cache key design: namespacing, hashing long keys
- In-process cache (functools.lru_cache, cachetools) + Redis layering
- CDN caching: Cache-Control, surrogate keys
- Vary header and cache fragmentation

--- Performance Optimization ---
- N+1 query problem: detect with query logging, fix with joins/eager loading
- Dataloader / batching pattern
- Database query optimization workflow: EXPLAIN ANALYZE → add index → measure
- Profiling: cProfile, py-spy for CPU, memory_profiler for memory
- Flamegraph reading
- Response compression: gzip, brotli
- HTTP keep-alive and connection reuse
- HTTP/2 multiplexing benefits
- Read replicas for read-heavy workloads
- Pagination: never SELECT * on large tables
- Background pre-computation for expensive queries

--- Rate Limiting ---
- Why rate limiting matters
- Algorithms: fixed window, sliding window, token bucket, leaky bucket
- Rate limiting per user, per IP, per endpoint
- Implementing with Redis (atomic increment + TTL)
- Returning 429 with Retry-After header
- Rate limiting in API Gateway vs application layer

--- Horizontal Scaling ---
- Stateless services: why state must be external (Redis, DB)
- Load balancing: round-robin, least connections, sticky sessions
- Session sharing across instances
- Sticky sessions and when to avoid them
- Database connection pool sizing under horizontal scale
- Little's law: throughput = concurrency / latency
- Amdahl's law: diminishing returns from parallelism

═══════════════════════════════════════════════════════
STAGE 7 – MICROSERVICES & DISTRIBUTED SYSTEMS
(Build systems of systems)
═══════════════════════════════════════════════════════

--- Microservices Fundamentals ---
- Why microservices (and why not): trade-offs vs monolith
- Service decomposition by business domain (DDD basics)
- Bounded contexts: each service owns its data
- Synchronous communication: REST, gRPC
- Asynchronous communication: events via message queue
- API Gateway pattern
- Service discovery basics
- Health checks: liveness vs readiness probes

--- gRPC ---
- Protocol Buffers: defining .proto files
- Service definitions and message types
- Unary, server streaming, client streaming, bidirectional streaming
- gRPC vs REST trade-offs
- gRPC-web for browser clients
- Error codes in gRPC

--- Distributed Systems Concepts ---
- CAP theorem: consistency, availability, partition tolerance
- BASE vs ACID
- Eventual consistency: what it means in practice
- Distributed transactions: 2PC and its problems
- Saga pattern: choreography vs orchestration
- Idempotency in distributed systems
- Exactly-once delivery: why it's hard
- At-least-once vs at-most-once delivery
- Distributed locking with Redis (Redlock)
- Clock skew and logical clocks (Lamport timestamps)

--- Resilience Patterns ---
- Circuit breaker: closed, open, half-open states
- Retry with exponential backoff and jitter
- Timeout propagation: always set timeouts on outbound calls
- Bulkhead: isolating resource pools per dependency
- Fallback strategies: cached data, degraded response
- Graceful degradation: serve partial data vs total failure
- Graceful shutdown: drain in-flight requests before stopping
- Cascading failure prevention

--- Event-Driven Architecture ---
- Event vs command vs query distinction
- Domain events: what happened in the past
- Event sourcing: state derived from event log
- CQRS: separate read and write models
- Choreography: services react to events independently
- Orchestration: central coordinator directs steps
- Schema evolution: adding fields, backward compatibility
- Consumer-driven contract testing (Pact)

═══════════════════════════════════════════════════════
STAGE 8 – AI / LLM INTEGRATION
(Build AI-powered backends)
═══════════════════════════════════════════════════════

--- LLM API Basics ---
- How chat completions work: system/user/assistant turns
- Token counting: what tokens are, cost estimation
- Max tokens and context window limits per model
- Temperature, top_p: controlling output randomness
- Handling rate limits: 429 errors, exponential backoff
- Streaming responses: why it matters for UX
- Forwarding LLM stream to client (streaming proxy)
- Model comparison: GPT-4o, Claude Sonnet, Gemini – trade-offs
- Provider failover strategy

--- Prompt Engineering for Backends ---
- System prompt design and guardrails
- Structured output prompting: JSON mode, response_format
- Few-shot examples in prompts
- Prompt injection awareness and basic mitigations
- Token optimization: removing unnecessary content
- Prompt versioning: storing prompts as config not code

--- Function / Tool Calling ---
- What tool calling is and how it works
- Defining tool schemas (name, description, parameters)
- Parsing tool call responses
- Multi-tool calls in one response
- Handling tool errors and returning results
- Designing tools that are safe to call

--- RAG Pipeline ---
- What RAG is and why it exists
- Document ingestion pipeline
- Chunking strategies: fixed, sentence, recursive, semantic
- Chunk size and overlap tuning
- Embedding models: OpenAI, sentence-transformers
- Vector databases: pgvector, Pinecone, Qdrant, Chroma
- Storing and retrieving embeddings
- Similarity search: cosine similarity
- Hybrid search: vector + BM25 keyword
- Reranking retrieved results
- Injecting retrieved context into prompt
- Metadata filtering in vector search
- Evaluating RAG: relevance, faithfulness, groundedness

--- Agent Design ---
- ReAct agent loop: Reason → Act → Observe → repeat
- Planning agents: plan-and-execute pattern
- Agent memory types: in-context, summary, vector store
- Max iteration limits and loop detection
- Error handling in agent loops
- LangChain / LlamaIndex vs custom orchestration
- When NOT to use agents (most cases)

--- LLM Ops ---
- Logging every LLM call: prompt, response, tokens, cost, latency
- Tracing with Langfuse, LangSmith, or Helicone
- Cost tracking per user / per tenant
- Exact-match caching for repeated prompts
- Semantic caching for similar prompts
- Latency monitoring: P50, P95, P99
- Prompt A/B testing
- Regression testing: detect when output quality changes

═══════════════════════════════════════════════════════
STAGE 9 – SECURITY IN DEPTH
(Stop being the reason for the breach)
═══════════════════════════════════════════════════════

- SQL injection: how it works, parameterized queries, ORM protections
- NoSQL injection patterns
- XSS: why it's a backend concern too (API responses to SPAs)
- CSRF: tokens, SameSite cookies
- SSRF: block when making outbound HTTP calls, allowlist domains
- Mass assignment: never bind request body directly to DB model
- Insecure deserialization: don't pickle untrusted data
- Timing attacks: use hmac.compare_digest for token comparison
- Input validation at every boundary (never trust client)
- Secure headers: HSTS, X-Content-Type-Options, CSP
- Dependency auditing: pip-audit, Dependabot, Snyk
- Container image scanning: Trivy, Grype
- Least privilege: DB users, IAM roles, service accounts
- Secrets management: never in code, use Vault or cloud secret managers
- Secrets rotation without downtime
- TLS configuration: enforce TLS 1.2+, cipher suite selection
- Audit logging: who did what, when, from where
- OWASP Top 10: read and understand each one

═══════════════════════════════════════════════════════
STAGE 10 – OBSERVABILITY & OPERATIONS
(Know what your system is doing)
═══════════════════════════════════════════════════════

- Structured JSON logging in production
- Correlation IDs: trace_id across all services and logs
- Log sampling for high-volume endpoints
- OpenTelemetry: traces, spans, metrics, logs – instrumentation
- Distributed tracing: following a request across services
- Prometheus metrics: counter, gauge, histogram, summary
- RED method: Rate, Errors, Duration per service
- USE method: Utilization, Saturation, Errors per resource
- Histogram bucket design for latency (don't use defaults blindly)
- Grafana: building useful dashboards
- Alerting: SLO-based alerts, not just threshold alerts
- SLI / SLO / SLA / Error budget concepts
- Synthetic monitoring: probing production from outside
- On-call: runbooks, escalation paths, postmortem process
- Incident response: triage → mitigate → fix → document

═══════════════════════════════════════════════════════
STAGE 11 – KUBERNETES & CLOUD
(Run at scale)
═══════════════════════════════════════════════════════

--- Kubernetes ---
- Pods, Deployments, ReplicaSets
- Services: ClusterIP, NodePort, LoadBalancer
- ConfigMaps and Secrets
- Persistent Volumes and claims
- Liveness, readiness, startup probes
- Resource requests and limits (always set both)
- Horizontal Pod Autoscaler: CPU and custom metrics (KEDA)
- Rolling updates and rollback
- PodDisruptionBudget for zero-downtime deploys
- Ingress and ingress controllers (nginx, traefik)
- Namespaces and RBAC in Kubernetes
- Network policies for traffic isolation
- StatefulSets for databases
- Helm: writing and using charts
- kubectl commands for debugging: logs, exec, describe, events

--- CI/CD ---
- Pipeline stages: lint → test → build → scan → deploy
- GitOps with ArgoCD or Flux
- Secrets in CI: never in repo, use CI secret store
- Artifact versioning: semantic version or commit SHA
- Blue/Green vs Canary vs Rolling deployments
- Automated rollback on failed health checks

═══════════════════════════════════════════════════════
STAGE 12 – SYSTEM DESIGN & SENIOR SKILLS
(Think at architecture level)
═══════════════════════════════════════════════════════

--- System Design Practice (design these end to end) ---
- URL shortener
- Rate limiter service
- Notification service at scale (email/SMS/push)
- File upload service with async processing pipeline
- Auth service: tokens, sessions, refresh
- Job scheduling system (cron-like at scale)
- Real-time chat with presence and history
- Feed / timeline generation: fanout on write vs read
- Search service: full-text + filters + ranking
- Audit log system: append-only, tamper-evident
- Multi-tenant SaaS backend: data isolation per tenant
- AI chat backend: streaming, history, RAG, tool use
- Webhook delivery system: retries, ordering, failure handling

--- Design Process (for every system) ---
- Clarify requirements: functional and non-functional
- Estimate scale: QPS, storage, bandwidth, DAU
- Define data model before anything else
- Identify read/write ratio and design accordingly
- Plan failure modes explicitly
- State where and why: cache, queue, CDN, replica
- Discuss trade-offs, not just solutions
- Document decisions as ADRs (Architecture Decision Records)

--- Engineering Practices ---
- Writing technical specs / RFCs before building
- Code review: giving constructive feedback, not just finding bugs
- Technical debt: identifying, quantifying, prioritizing paydown
- Estimating tasks: breaking down work, surfacing unknowns early
- Incremental delivery: feature flags, dark launches, strangler fig
- On-call incident response: triage, mitigation, RCA
- Postmortem culture: blameless, focus on systems not people
- Mentoring juniors: code review teaching, pair programming
- Communicating trade-offs to non-engineers clearly