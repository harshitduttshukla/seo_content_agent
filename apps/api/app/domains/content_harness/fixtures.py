"""Golden test cases for repeatable Content Harness evaluations."""

from uuid import UUID

from app.domains.content.brief_schemas import BrandRequirements, InternalLinkTarget
from app.domains.content_harness.schemas import ContentHarnessInput

DUMMY_PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")

GOLDEN_TEST_CASES: dict[str, ContentHarnessInput] = {
    "case-1-normal-seo": ContentHarnessInput(
        project_id=DUMMY_PROJECT_ID,
        name="Case 1: Normal SEO Article",
        primary_keyword="fleet vehicle tracking",
        secondary_keywords=["gps tracking", "fleet monitoring", "vehicle telematics"],
        search_intent="INFORMATIONAL",
        target_audience="Fleet managers and logistics operations leads",
        target_word_count=1200,
        required_topics=[
            "How Fleet Vehicle Tracking Works",
            "Key Hardware and Software Components",
            "Operational and Cost Benefits",
            "Implementation Best Practices",
        ],
        required_questions=[
            "What is fleet vehicle tracking?",
            "How does GPS tracking improve route efficiency?",
            "What are the typical cost savings?",
        ],
        brand_rules=BrandRequirements(
            tone="Professional, practical, authoritative",
            voice="Operations expert",
            style="Actionable, structured, clear paragraphs",
            words_to_avoid=["cheap", "effortless", "cure-all"],
            formatting_rules=["Use descriptive H2 headings", "Include bullet points for key takeaways"],
        ),
        internal_link_targets=[
            InternalLinkTarget(
                url="/telematics-platform",
                anchor_text="telematics platform",
                reason="Connect core product architecture",
            )
        ],
        website_context="FleetIQ Telematics provides real-time GPS tracking, automated driver logging, and vehicle diagnostics for medium to large enterprise fleets.",
        prompt_version="v1",
    ),
    "case-2-multiple-keywords": ContentHarnessInput(
        project_id=DUMMY_PROJECT_ID,
        name="Case 2: Multiple Keywords",
        primary_keyword="fleet tracking software",
        secondary_keywords=[
            "vehicle tracking",
            "fleet management software",
            "gps fleet tracking system",
            "driver safety monitoring",
        ],
        search_intent="COMMERCIAL",
        target_audience="VP of Fleet Logistics and Supply Chain Directors",
        target_word_count=1500,
        required_topics=[
            "Essential Software Features for Modern Fleets",
            "Integration with Dispatch and Maintenance",
            "ROI and Fuel Reduction Metrics",
            "Selecting the Right Software Platform",
        ],
        required_questions=[
            "What features should fleet tracking software include?",
            "How does fleet management software reduce fuel consumption?",
            "Can GPS tracking systems integrate with existing ERP tools?",
        ],
        brand_rules=BrandRequirements(
            tone="Authoritative, data-driven, strategic",
            voice="Technology consultant",
            style="Clear headings, data points, concise summaries",
            words_to_avoid=["hack", "cheap", "overnight results"],
            formatting_rules=["Include an evaluation criteria checklist"],
        ),
        internal_link_targets=[
            InternalLinkTarget(
                url="/features/gps-hardware",
                anchor_text="GPS hardware integrations",
                reason="Guide readers to hardware compatibility guide",
            ),
            InternalLinkTarget(
                url="/pricing",
                anchor_text="enterprise fleet pricing",
                reason="Commercial intent conversion path",
            ),
        ],
        website_context="Our software connects directly to onboard OBD-II and CAN bus ports to monitor engine health, driver safety events, and idle times.",
        prompt_version="v2",
    ),
    "case-3-brand-rules": ContentHarnessInput(
        project_id=DUMMY_PROJECT_ID,
        name="Case 3: Strict Brand Compliance & Forbidden Words",
        primary_keyword="enterprise telematics solutions",
        secondary_keywords=["fleet diagnostics", "asset tracking"],
        search_intent="INFORMATIONAL",
        target_audience="C-Suite executives and Transportation Directors",
        target_word_count=1000,
        required_topics=[
            "Data Security and Cloud Telematics",
            "Compliance with Transportation Regulations",
            "Scalability for Multi-Depot Fleets",
        ],
        required_questions=[
            "How is telematics data secured?",
            "How does telematics assist with regulatory compliance?",
        ],
        brand_rules=BrandRequirements(
            tone="Professional, practical, clear",
            voice="Executive enterprise advisor",
            style="Polished, corporate, rigorous",
            words_to_avoid=["cheap", "miracle", "guaranteed", "easy money", "hacks"],
            formatting_rules=["No colloquialisms or informal contractions"],
        ),
        internal_link_targets=[],
        website_context="Acme Telematics maintains SOC2 Type II compliance and 99.99% uptime for global logistics enterprises.",
        prompt_version="v2",
    ),
    "case-4-internal-linking": ContentHarnessInput(
        project_id=DUMMY_PROJECT_ID,
        name="Case 4: Internal Linking Verification",
        primary_keyword="fleet maintenance scheduling",
        secondary_keywords=["preventative maintenance", "vehicle inspections"],
        search_intent="INFORMATIONAL",
        target_audience="Maintenance supervisors and shop managers",
        target_word_count=1100,
        required_topics=[
            "Automated Preventative Maintenance Scheduling",
            "Pre-Trip Inspection Checklists",
            "Reducing Unscheduled Vehicle Downtime",
        ],
        required_questions=[
            "How to automate maintenance triggers based on mileage?",
            "What are the best practices for digital vehicle inspections?",
        ],
        brand_rules=BrandRequirements(
            tone="Helpful, technical, pragmatic",
            voice="Certified maintenance specialist",
            style="Step-by-step guidance",
            words_to_avoid=["foolproof", "instant fix"],
        ),
        internal_link_targets=[
            InternalLinkTarget(
                url="/features/real-time-gps",
                anchor_text="real-time GPS tracking",
                reason="Cross link to GPS tracking capabilities",
            ),
            InternalLinkTarget(
                url="/solutions/route-optimization",
                anchor_text="route optimization tools",
                reason="Connect route efficiency to engine wear",
            ),
            InternalLinkTarget(
                url="/resources/inspection-checklist",
                anchor_text="pre-trip inspection checklist",
                reason="Provide downloadable resource",
            ),
        ],
        website_context="FleetIQ includes automated maintenance scheduling triggered by actual engine hours and odometer readings.",
        prompt_version="v2",
    ),
    "case-5-missing-context": ContentHarnessInput(
        project_id=DUMMY_PROJECT_ID,
        name="Case 5: Sparse/Missing Context Factual Handling",
        primary_keyword="autonomous freight platooning",
        secondary_keywords=["connected truck technology", "v2v communications"],
        search_intent="INFORMATIONAL",
        target_audience="Future transport researchers and logistics innovators",
        target_word_count=1000,
        required_topics=[
            "V2V Communication Standards",
            "Aerodynamic Fuel Efficiency Gains",
            "Current Regulatory Status in North America",
        ],
        required_questions=[
            "What is autonomous freight platooning?",
            "What are the primary safety considerations?",
        ],
        brand_rules=BrandRequirements(
            tone="Objective, analytical, forward-looking",
            voice="Industry research analyst",
            style="Balanced technology review",
            words_to_avoid=["revolutionary", "disrupts everything"],
        ),
        internal_link_targets=[],
        website_context="",  # Intentionally empty to test model restraint
        prompt_version="v1",
    ),
    "case-6-invalid-output": ContentHarnessInput(
        project_id=DUMMY_PROJECT_ID,
        name="Case 6: Malformed Output & Failure Handling",
        primary_keyword="telematics hardware failure",
        secondary_keywords=["device error"],
        search_intent="INFORMATIONAL",
        target_audience="Technicians",
        target_word_count=500,
        required_topics=["Diagnostic codes"],
        required_questions=["How to reset device?"],
        brand_rules=BrandRequirements(
            tone="Technical",
            voice="Diagnostic technician",
            words_to_avoid=["cheap"],
        ),
        internal_link_targets=[],
        website_context="Diagnostics guide.",
        prompt_version="v1",
    ),
}
