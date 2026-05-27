-- =============================================================================
-- init.sql — Bootstrap para Postgres limpo (docker volume novo)
-- =============================================================================
-- Montado automaticamente via docker-compose.dev.yml em
-- /docker-entrypoint-initdb.d/init.sql
--
-- Executado APENAS na primeira inicialização (volume vazio).
-- Para forçar re-execução: docker compose down -v && docker compose up -d
-- =============================================================================

-- Extensões necessárias (uuid-ossp para uuid_generate_v4, pgcrypto para gen_random_uuid)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Schemas dos 22 microsserviços
CREATE SCHEMA IF NOT EXISTS address;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE SCHEMA IF NOT EXISTS asaas;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS candidate;
CREATE SCHEMA IF NOT EXISTS commissions;
CREATE SCHEMA IF NOT EXISTS coordinator;
CREATE SCHEMA IF NOT EXISTS documents;
CREATE SCHEMA IF NOT EXISTS enrollment;
CREATE SCHEMA IF NOT EXISTS fees;
CREATE SCHEMA IF NOT EXISTS hub;
CREATE SCHEMA IF NOT EXISTS infinitepay;
CREATE SCHEMA IF NOT EXISTS jwt;
CREATE SCHEMA IF NOT EXISTS lead;
CREATE SCHEMA IF NOT EXISTS notify;
CREATE SCHEMA IF NOT EXISTS otp;
CREATE SCHEMA IF NOT EXISTS profiles;
CREATE SCHEMA IF NOT EXISTS promoter;
CREATE SCHEMA IF NOT EXISTS roles;
CREATE SCHEMA IF NOT EXISTS staff;
CREATE SCHEMA IF NOT EXISTS student;
CREATE SCHEMA IF NOT EXISTS training;
