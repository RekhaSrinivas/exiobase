
CREATE OR REPLACE  FUNCTION get_trade(
    p_year         int[] DEFAULT NULL,
    p_region1      char(2)[] DEFAULT NULL,
    p_region2      char(2)[] DEFAULT NULL,
    p_industry1    varchar(25)[] DEFAULT NULL,
    p_industry2    varchar(25)[] DEFAULT NULL,
    p_amount_min   numeric(20,4) DEFAULT NULL,
    p_amount_max   numeric(20,4) DEFAULT NULL
)
RETURNS SETOF trade
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
      *
  FROM trade AS t
  WHERE (p_year    IS NULL OR cardinality(p_year)=0    OR t.year     = ANY(p_year))
    AND (p_region1 IS NULL OR cardinality(p_region1)=0 OR t.region1  = ANY(p_region1))
    AND (p_region2 IS NULL OR cardinality(p_region2)=0 OR t.region2  = ANY(p_region2))
    AND (p_industry1 IS NULL OR cardinality(p_industry1)=0 OR t.industry1 = ANY(p_industry1))
    AND (p_industry2 IS NULL OR cardinality(p_industry2)=0 OR t.industry2 = ANY(p_industry2))
    AND (p_amount_min IS NULL OR t.amount >= p_amount_min)
    AND (p_amount_max IS NULL OR t.amount <= p_amount_max);
END;
$$;
