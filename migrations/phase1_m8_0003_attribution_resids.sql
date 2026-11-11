-- Attribution scoring reads daily residuals for basket comparison inputs.
GRANT USAGE ON SCHEMA marketstate TO role_ingest;
GRANT SELECT ON marketstate.daily TO role_ingest;
