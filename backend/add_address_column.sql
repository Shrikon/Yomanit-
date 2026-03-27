ALTER TABLE indexes ADD COLUMN IF NOT EXISTS address VARCHAR(300);
COMMENT ON COLUMN indexes.address IS 'כתובת החוזה/המנוי המקורית מהקובץ';
COMMENT ON COLUMN indexes.connection_name IS 'שם החיבור הפנימי של הרשות';
SELECT 'OK' AS status;
