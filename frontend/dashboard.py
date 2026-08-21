"""Streamlit Dashboard Interface for Smart Resume Screener.

Strict isolation: Communicates ONLY through FastAPI REST API endpoints via `ScreenerAPIClient`.
Zero imports from SQLAlchemy, database models, or backend services.
Zero score recalculation or re-sorting logic in frontend.
"""

import streamlit as st
from frontend.api_client import APIClientError, APIConnectionError, APITimeoutError, APIHTTPError, ScreenerAPIClient

# Page configuration
st.set_page_config(
    page_title="Smart Resume Screener",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for UI polish
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .badge-strong {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
    }
    .badge-potential {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
    }
    .badge-weak {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
    }
    .skill-pill {
        display: inline-block;
        background-color: #E2E8F0;
        color: #334155;
        padding: 2px 8px;
        border-radius: 6px;
        margin: 2px;
        font-size: 0.85rem;
    }
    .skill-req {
        background-color: #DBEAFE;
        color: #1E40AF;
    }
    .skill-pref {
        background-color: #F3E8FF;
        color: #6B21A8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_api_client() -> ScreenerAPIClient:
    """Get singleton cached ScreenerAPIClient to avoid connection churn across reruns."""
    return ScreenerAPIClient()


client = get_api_client()

# Header & Health Check
st.markdown('<div class="main-title">Smart Resume Screener</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">AI-Powered Resume Parsing, Deterministic Matching & Semantic Evaluation</div>', unsafe_allow_html=True)

# Sidebar System Health
with st.sidebar:
    st.header("System Status")
    try:
        health = client.health_check()
        st.success(f"Backend API: Connected ({client.base_url})")
    except APIConnectionError:
        st.error(f"Backend API: Disconnected ({client.base_url})")
    except Exception as err:
        st.warning(f"Backend API: Error ({err})")

    st.markdown("---")
    st.caption("Smart Resume Screener v0.1.0")

# Main Navigation Tabs
tab_resumes, tab_jobs, tab_match, tab_shortlist = st.tabs(
    ["📤 Resume Upload", "💼 Job Description", "⚖️ Match Evaluation", "🏆 Shortlist Dashboard"]
)

# ----------------------------------------------------
# TAB 1: RESUME UPLOAD
# ----------------------------------------------------
with tab_resumes:
    st.subheader("Ingest Candidate Resume")
    uploaded_file = st.file_uploader("Upload Resume PDF file", type=["pdf"], key="resume_uploader")

    if st.button("Ingest Candidate Resume", type="primary", key="btn_ingest_resume"):
        if not uploaded_file:
            st.error("Please select a PDF file to upload.")
        else:
            with st.spinner("Extracting text and candidate profile..."):
                try:
                    file_bytes = uploaded_file.read()
                    filename = uploaded_file.name
                    candidate = client.upload_resume(file_bytes=file_bytes, filename=filename)

                    st.success(f"Candidate #{candidate.get('candidate_id')} ingested successfully!")

                    # Display extracted candidate details
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Candidate ID", candidate.get("candidate_id"))
                    col2.metric("Name", candidate.get("name") or "Unextracted")
                    col3.metric("Email", candidate.get("email") or "Unextracted")

                    st.markdown("**Phone:** " + (candidate.get("phone") or "N/A"))

                    st.markdown("### Extracted Skills")
                    skills = candidate.get("skills") or []
                    if skills:
                        pills_html = "".join([f'<span class="skill-pill">{s}</span>' for s in skills])
                        st.markdown(pills_html, unsafe_allow_html=True)
                    else:
                        st.info("No explicit skills extracted.")

                    st.markdown("### Experience")
                    exp_list = candidate.get("experience") or []
                    if exp_list:
                        for exp in exp_list:
                            st.write(f"- **{exp.get('role') or 'Role'}** at **{exp.get('company') or 'Company'}** ({exp.get('duration') or 'N/A'})")
                            if exp.get("description"):
                                st.caption(exp["description"])
                    else:
                        st.info("No work experience entries recorded.")

                    st.markdown("### Education")
                    edu_list = candidate.get("education") or []
                    if edu_list:
                        for edu in edu_list:
                            st.write(f"- **{edu.get('degree') or 'Degree'}**, {edu.get('institution') or 'Institution'} ({edu.get('year') or 'N/A'})")
                    else:
                        st.info("No education entries recorded.")

                except APIHTTPError as err:
                    if err.status_code == 400:
                        st.error(f"Invalid PDF File: {err.detail}")
                    elif err.status_code == 422:
                        st.error(f"Resume Extraction Failure: {err.detail}")
                    elif err.status_code == 503:
                        st.warning(f"Service Unavailable (LLM Down): {err.detail}")
                    else:
                        st.error(f"API Error ({err.status_code}): {err.detail}")
                except (APIConnectionError, APITimeoutError) as err:
                    st.error(f"Backend Unavailable: {err.message}")
                except Exception as err:
                    st.error(f"Unexpected Error: {err}")

# ----------------------------------------------------
# TAB 2: JOB POSTING
# ----------------------------------------------------
with tab_jobs:
    st.subheader("Ingest Job Description")
    job_desc_input = st.text_area(
        "Paste Job Description text",
        height=200,
        placeholder="We are looking for a Senior Software Engineer with 5+ years of experience in Python, FastAPI...",
        key="job_desc_area",
    )

    if st.button("Ingest Job Posting", type="primary", key="btn_ingest_job"):
        if not job_desc_input.strip():
            st.error("Please enter a valid job description.")
        else:
            with st.spinner("Extracting structured job profile..."):
                try:
                    job = client.create_job(description=job_desc_input)
                    st.success(f"Job Posting #{job.get('job_id')} created successfully!")

                    st.markdown(f"### {job.get('title') or 'Untitled Position'}")

                    col1, col2 = st.columns(2)
                    col1.metric("Job ID", job.get("job_id"))
                    col2.metric("Experience Required", f"{job.get('experience_required') or 0.0} yrs")

                    st.markdown("**Education Requirement:** " + (job.get("education") or "Not specified"))

                    col_req, col_pref = st.columns(2)
                    with col_req:
                        st.markdown("#### Required Skills")
                        req_skills = job.get("required_skills") or []
                        if req_skills:
                            html_req = "".join([f'<span class="skill-pill skill-req">{s}</span>' for s in req_skills])
                            st.markdown(html_req, unsafe_allow_html=True)
                        else:
                            st.info("No required skills specified.")

                    with col_pref:
                        st.markdown("#### Preferred Skills")
                        pref_skills = job.get("preferred_skills") or []
                        if pref_skills:
                            html_pref = "".join([f'<span class="skill-pill skill-pref">{s}</span>' for s in pref_skills])
                            st.markdown(html_pref, unsafe_allow_html=True)
                        else:
                            st.info("No preferred skills specified.")

                    st.markdown("#### Responsibilities")
                    resps = job.get("responsibilities") or []
                    if resps:
                        for r in resps:
                            st.write(f"- {r}")
                    else:
                        st.info("No responsibilities listed.")

                except APIHTTPError as err:
                    if err.status_code == 400:
                        st.error(f"Invalid Job Input: {err.detail}")
                    elif err.status_code == 422:
                        st.error(f"Job Extraction Failure: {err.detail}")
                    else:
                        st.error(f"API Error ({err.status_code}): {err.detail}")
                except (APIConnectionError, APITimeoutError) as err:
                    st.error(f"Backend Unavailable: {err.message}")
                except Exception as err:
                    st.error(f"Unexpected Error: {err}")

# ----------------------------------------------------
# TAB 3: MATCH EVALUATION
# ----------------------------------------------------
with tab_match:
    st.subheader("Evaluate Candidate vs Job Posting")

    col_c, col_j = st.columns(2)
    with col_c:
        cand_id_input = st.number_input("Candidate ID", min_value=1, step=1, key="match_cand_id")
    with col_j:
        job_id_input = st.number_input("Job ID", min_value=1, step=1, key="match_job_id")

    if st.button("Evaluate Candidate", type="primary", key="btn_evaluate_match"):
        with st.spinner("Running deterministic & LLM semantic score fusion..."):
            try:
                match_res = client.create_match(candidate_id=int(cand_id_input), job_id=int(job_id_input))

                st.success("Match evaluation completed successfully!")

                # Status Badge & Final Score
                status_str = match_res.get("status") or "Weak Match"
                badge_class = "badge-weak"
                if status_str == "Strong Match":
                    badge_class = "badge-strong"
                elif status_str == "Potential Match":
                    badge_class = "badge-potential"

                st.markdown(f'### Qualification Status: <span class="{badge_class}">{status_str}</span>', unsafe_allow_html=True)
                st.write("")

                # Score Breakdown Metrics
                scores = match_res.get("score_breakdown") or {}
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Final Score", f"{scores.get('final_score', 0.0):.1f} / 100")
                m2.metric("Skill Score", f"{scores.get('skill_score', 0.0):.1f}")
                m3.metric("Experience Score", f"{scores.get('experience_score', 0.0):.1f}")
                m4.metric("Education Score", f"{scores.get('education_score', 0.0):.1f}")
                m5.metric("Semantic Score", f"{scores.get('semantic_score', 0.0):.1f}")

                # Skill Match Details
                st.markdown("---")
                c_req, c_missing, c_pref = st.columns(3)
                with c_req:
                    st.markdown("#### Matched Required Skills")
                    for s in match_res.get("matched_required_skills") or []:
                        st.success(f"✓ {s}")
                with c_missing:
                    st.markdown("#### Missing Required Skills")
                    for s in match_res.get("missing_required_skills") or []:
                        st.error(f"✗ {s}")
                with c_pref:
                    st.markdown("#### Matched Preferred Skills")
                    for s in match_res.get("matched_preferred_skills") or []:
                        st.info(f"★ {s}")

                # Strengths & Gaps
                st.markdown("---")
                cs, cg = st.columns(2)
                with cs:
                    st.markdown("#### Strengths")
                    for st_item in match_res.get("strengths") or []:
                        st.write(f"- {st_item}")
                with cg:
                    st.markdown("#### Gaps / Deficiencies")
                    for gap_item in match_res.get("gaps") or []:
                        st.write(f"- {gap_item}")

                # Justification
                st.markdown("---")
                st.markdown("#### Evaluation Justification")
                st.write(match_res.get("justification") or "No justification provided.")

            except APIHTTPError as err:
                if err.status_code == 404:
                    st.error(f"Resource Not Found (404): {err.detail}")
                elif err.status_code == 503:
                    st.error(f"Semantic Service Unavailable (HTTP 503): {err.detail}")
                    st.warning("Match evaluation was cancelled. No Match record was persisted.")
                else:
                    st.error(f"API Error ({err.status_code}): {err.detail}")
            except (APIConnectionError, APITimeoutError) as err:
                st.error(f"Backend Unavailable: {err.message}")
            except Exception as err:
                st.error(f"Unexpected Error: {err}")

# ----------------------------------------------------
# TAB 4: SHORTLIST DASHBOARD
# ----------------------------------------------------
with tab_shortlist:
    st.subheader("Job Candidate Shortlist & Ranking")

    shortlist_job_id = st.number_input("Enter Job ID to view shortlist", min_value=1, step=1, key="shortlist_job_id")

    if st.button("Get Shortlist", type="primary", key="btn_get_shortlist"):
        with st.spinner("Retrieving ranked candidates..."):
            try:
                shortlist_data = client.get_shortlist(job_id=int(shortlist_job_id))
                candidates = shortlist_data.get("candidates") or []

                if not candidates:
                    st.info(f"No evaluated candidates found for Job #{shortlist_job_id}.")
                else:
                    st.success(f"Retrieved {len(candidates)} ranked candidates for Job #{shortlist_job_id}.")

                    # Format table data EXACTLY in backend-provided order (DO NOT RE-SORT!)
                    table_rows = []
                    for idx, cand in enumerate(candidates, start=1):
                        table_rows.append({
                            "Rank": f"#{idx}",
                            "Candidate ID": cand.get("candidate_id"),
                            "Candidate Name": cand.get("candidate_name"),
                            "Final Score": f"{cand.get('final_score', 0.0):.1f}",
                            "Status": cand.get("status"),
                            "Justification": cand.get("justification"),
                        })

                    st.dataframe(table_rows, use_container_width=True)

            except APIHTTPError as err:
                if err.status_code == 404:
                    st.error(f"Job Not Found (404): {err.detail}")
                else:
                    st.error(f"API Error ({err.status_code}): {err.detail}")
            except (APIConnectionError, APITimeoutError) as err:
                st.error(f"Backend Unavailable: {err.message}")
            except Exception as err:
                st.error(f"Unexpected Error: {err}")
