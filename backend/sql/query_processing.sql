create or replace function match_review_chunks(
  query_embedding vector(1536),
  match_org_id uuid,
  match_feature_id uuid,
  match_count int default 4
)
returns table (
  review_id uuid,
  chunk_text text,
  similarity float
)
language sql stable
as $$
  select
    review_id,
    chunk_text,
    1 - (embedding <=> query_embedding) as similarity
  from review_chunks
  where org_id = match_org_id
    and feature_id = match_feature_id
  order by embedding <=> query_embedding
  limit match_count;
$$;
