--
-- PostgreSQL database dump
--

\restrict eBCKVyJa8EhlkZD9YbhWk8gp4D2vMDTb2oCTOrVeLfSspKcd6Pa2CPJCHnT9bIY

-- Dumped from database version 15.14 (Debian 15.14-1.pgdg13+1)
-- Dumped by pg_dump version 15.14 (Debian 15.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: protocol_requirements; Type: TABLE; Schema: public; Owner: sitesync
--

CREATE TABLE public.protocol_requirements (
    id integer NOT NULL,
    protocol_id integer NOT NULL,
    key character varying(128) NOT NULL,
    op character varying(8) NOT NULL,
    value text,
    weight integer NOT NULL,
    type character varying(16) NOT NULL,
    source_question text
);


ALTER TABLE public.protocol_requirements OWNER TO sitesync;

--
-- Name: protocol_requirements_id_seq; Type: SEQUENCE; Schema: public; Owner: sitesync
--

CREATE SEQUENCE public.protocol_requirements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.protocol_requirements_id_seq OWNER TO sitesync;

--
-- Name: protocol_requirements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sitesync
--

ALTER SEQUENCE public.protocol_requirements_id_seq OWNED BY public.protocol_requirements.id;


--
-- Name: protocols; Type: TABLE; Schema: public; Owner: sitesync
--

CREATE TABLE public.protocols (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    sponsor character varying(255),
    disease character varying(255),
    phase character varying(50),
    nct_id character varying(32),
    notes text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.protocols OWNER TO sitesync;

--
-- Name: protocols_id_seq; Type: SEQUENCE; Schema: public; Owner: sitesync
--

CREATE SEQUENCE public.protocols_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.protocols_id_seq OWNER TO sitesync;

--
-- Name: protocols_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sitesync
--

ALTER SEQUENCE public.protocols_id_seq OWNED BY public.protocols.id;


--
-- Name: site_patient_capabilities; Type: TABLE; Schema: public; Owner: sitesync
--

CREATE TABLE public.site_patient_capabilities (
    id integer NOT NULL,
    site_id integer NOT NULL,
    indication_code character varying(64),
    indication_label character varying(255),
    age_min_years integer,
    age_max_years integer,
    sex character varying(8),
    annual_eligible_patients integer,
    notes text,
    evidence_url text
);


ALTER TABLE public.site_patient_capabilities OWNER TO sitesync;

--
-- Name: site_patient_capabilities_id_seq; Type: SEQUENCE; Schema: public; Owner: sitesync
--

CREATE SEQUENCE public.site_patient_capabilities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.site_patient_capabilities_id_seq OWNER TO sitesync;

--
-- Name: site_patient_capabilities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sitesync
--

ALTER SEQUENCE public.site_patient_capabilities_id_seq OWNED BY public.site_patient_capabilities.id;


--
-- Name: site_truth_fields; Type: TABLE; Schema: public; Owner: sitesync
--

CREATE TABLE public.site_truth_fields (
    id integer NOT NULL,
    site_id integer NOT NULL,
    key character varying(128) NOT NULL,
    value text NOT NULL,
    unit character varying(32),
    evidence_required boolean
);


ALTER TABLE public.site_truth_fields OWNER TO sitesync;

--
-- Name: site_truth_fields_id_seq; Type: SEQUENCE; Schema: public; Owner: sitesync
--

CREATE SEQUENCE public.site_truth_fields_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.site_truth_fields_id_seq OWNER TO sitesync;

--
-- Name: site_truth_fields_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sitesync
--

ALTER SEQUENCE public.site_truth_fields_id_seq OWNED BY public.site_truth_fields.id;


--
-- Name: sites; Type: TABLE; Schema: public; Owner: sitesync
--

CREATE TABLE public.sites (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    address text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.sites OWNER TO sitesync;

--
-- Name: sites_id_seq; Type: SEQUENCE; Schema: public; Owner: sitesync
--

CREATE SEQUENCE public.sites_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sites_id_seq OWNER TO sitesync;

--
-- Name: sites_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sitesync
--

ALTER SEQUENCE public.sites_id_seq OWNED BY public.sites.id;


--
-- Name: protocol_requirements id; Type: DEFAULT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.protocol_requirements ALTER COLUMN id SET DEFAULT nextval('public.protocol_requirements_id_seq'::regclass);


--
-- Name: protocols id; Type: DEFAULT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.protocols ALTER COLUMN id SET DEFAULT nextval('public.protocols_id_seq'::regclass);


--
-- Name: site_patient_capabilities id; Type: DEFAULT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.site_patient_capabilities ALTER COLUMN id SET DEFAULT nextval('public.site_patient_capabilities_id_seq'::regclass);


--
-- Name: site_truth_fields id; Type: DEFAULT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.site_truth_fields ALTER COLUMN id SET DEFAULT nextval('public.site_truth_fields_id_seq'::regclass);


--
-- Name: sites id; Type: DEFAULT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.sites ALTER COLUMN id SET DEFAULT nextval('public.sites_id_seq'::regclass);


--
-- Data for Name: protocol_requirements; Type: TABLE DATA; Schema: public; Owner: sitesync
--

COPY public.protocol_requirements (id, protocol_id, key, op, value, weight, type, source_question) FROM stdin;
1	1	patient_sex	in	['all', 'all']	1	objective	Sex eligibility: all
\.


--
-- Data for Name: protocols; Type: TABLE DATA; Schema: public; Owner: sitesync
--

COPY public.protocols (id, name, sponsor, disease, phase, nct_id, notes, created_at) FROM stdin;
1	Follow-up of Breast Cancer and Multiple Myeloma Patients Previously Enrolled in NIH Gene Therapy Studies	\N	\N	\N	NCT00427726	Imported from CT.gov NCT NCT00427726	2025-09-13 02:44:17.522204+00
\.


--
-- Data for Name: site_patient_capabilities; Type: TABLE DATA; Schema: public; Owner: sitesync
--

COPY public.site_patient_capabilities (id, site_id, indication_code, indication_label, age_min_years, age_max_years, sex, annual_eligible_patients, notes, evidence_url) FROM stdin;
1	1	\N	Solid tumor	18	80	all	120	\N	\N
\.


--
-- Data for Name: site_truth_fields; Type: TABLE DATA; Schema: public; Owner: sitesync
--

COPY public.site_truth_fields (id, site_id, key, value, unit, evidence_required) FROM stdin;
13	1	ct_scanners	2	units	t
14	1	ehr_vendor	Epic	\N	f
15	1	crc_fte	1.5	FTE	f
16	1	onc_trials_last_12mo	3	trials	f
17	3	ct_scanners	0	units	t
18	3	ehr_vendor	Cerner	\N	f
19	3	crc_fte	0.8	FTE	f
20	3	onc_trials_last_12mo	1	trials	f
21	4	ct_scanners	1	units	t
22	4	ehr_vendor	Athena	\N	f
23	4	crc_fte	2.0	FTE	f
24	4	onc_trials_last_12mo	5	trials	f
\.


--
-- Data for Name: sites; Type: TABLE DATA; Schema: public; Owner: sitesync
--

COPY public.sites (id, name, address, created_at) FROM stdin;
1	Brown Uni Site	Van Wickle St	2025-09-12 03:30:49.981141+00
2	UCLA Health	Gayley Ave	2025-09-12 03:45:54.860782+00
3	Providence Research Center	123 Hope St	2025-09-12 03:51:48.26003+00
4	East Bay Clinical	456 Bay Ave	2025-09-12 03:51:48.268995+00
\.


--
-- Name: protocol_requirements_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sitesync
--

SELECT pg_catalog.setval('public.protocol_requirements_id_seq', 1, true);


--
-- Name: protocols_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sitesync
--

SELECT pg_catalog.setval('public.protocols_id_seq', 1, true);


--
-- Name: site_patient_capabilities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sitesync
--

SELECT pg_catalog.setval('public.site_patient_capabilities_id_seq', 1, true);


--
-- Name: site_truth_fields_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sitesync
--

SELECT pg_catalog.setval('public.site_truth_fields_id_seq', 24, true);


--
-- Name: sites_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sitesync
--

SELECT pg_catalog.setval('public.sites_id_seq', 4, true);


--
-- Name: protocol_requirements protocol_requirements_pkey; Type: CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.protocol_requirements
    ADD CONSTRAINT protocol_requirements_pkey PRIMARY KEY (id);


--
-- Name: protocols protocols_pkey; Type: CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.protocols
    ADD CONSTRAINT protocols_pkey PRIMARY KEY (id);


--
-- Name: site_patient_capabilities site_patient_capabilities_pkey; Type: CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.site_patient_capabilities
    ADD CONSTRAINT site_patient_capabilities_pkey PRIMARY KEY (id);


--
-- Name: site_truth_fields site_truth_fields_pkey; Type: CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.site_truth_fields
    ADD CONSTRAINT site_truth_fields_pkey PRIMARY KEY (id);


--
-- Name: sites sites_pkey; Type: CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_pkey PRIMARY KEY (id);


--
-- Name: ix_protocol_requirements_id; Type: INDEX; Schema: public; Owner: sitesync
--

CREATE INDEX ix_protocol_requirements_id ON public.protocol_requirements USING btree (id);


--
-- Name: ix_protocols_id; Type: INDEX; Schema: public; Owner: sitesync
--

CREATE INDEX ix_protocols_id ON public.protocols USING btree (id);


--
-- Name: ix_site_patient_capabilities_id; Type: INDEX; Schema: public; Owner: sitesync
--

CREATE INDEX ix_site_patient_capabilities_id ON public.site_patient_capabilities USING btree (id);


--
-- Name: protocol_requirements protocol_requirements_protocol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.protocol_requirements
    ADD CONSTRAINT protocol_requirements_protocol_id_fkey FOREIGN KEY (protocol_id) REFERENCES public.protocols(id) ON DELETE CASCADE;


--
-- Name: site_patient_capabilities site_patient_capabilities_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.site_patient_capabilities
    ADD CONSTRAINT site_patient_capabilities_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE CASCADE;


--
-- Name: site_truth_fields site_truth_fields_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: sitesync
--

ALTER TABLE ONLY public.site_truth_fields
    ADD CONSTRAINT site_truth_fields_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict eBCKVyJa8EhlkZD9YbhWk8gp4D2vMDTb2oCTOrVeLfSspKcd6Pa2CPJCHnT9bIY

