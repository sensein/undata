-- Enable pgvector for embedding similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for trigram-based fuzzy text matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;
