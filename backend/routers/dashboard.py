"""
Dashboard data router - SQLite version
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from schemas.dashboard import (
    DashboardResponse,
    KPICard,
    SufficiencyCard,
    ComplianceFlag,
    TrendDataPoint,
    BlockCard,
    BlockWithData,
    ApprovalClassification,
    ApprovalReadiness,
)
from schemas.kpi_details import KPIDetailsResponse
from config.information_blocks import get_information_blocks, get_block_description
from config.database import get_db, Batch, Block, ComplianceFlag as ComplianceFlagModel, close_db
from middleware.auth_middleware import get_current_user

router = APIRouter()


def _get_demo_dashboard_data(batch_id: str) -> DashboardResponse:
    """Return realistic demo dashboard data for demo batch IDs."""
    
    # Determine mode from batch_id
    if "aicte" in batch_id.lower():
        mode = "aicte"
        institution_name = "Indian Institute of Technology Delhi"
        kpi_cards = [
            KPICard(name="AICTE Overall Score", value=78.5, label="Good", color="blue"),
            KPICard(name="Faculty-Student Ratio", value=85.2, label="Excellent", color="blue"),
            KPICard(name="Infrastructure Score", value=72.0, label="Good", color="blue"),
            KPICard(name="PhD Faculty %", value=68.5, label="Good", color="orange"),
            KPICard(name="Placement Rate", value=92.3, label="Excellent", color="blue"),
        ]
        kpis = {"overall_score": 78.5, "fsr_score": 85.2, "infrastructure_score": 72.0, "phd_faculty": 68.5, "placement_rate": 92.3}
    elif "ugc" in batch_id.lower():
        mode = "ugc"
        institution_name = "Delhi University - North Campus"
        kpi_cards = [
            KPICard(name="UGC Overall Score", value=82.1, label="Excellent", color="blue"),
            KPICard(name="Research Output", value=75.5, label="Good", color="blue"),
            KPICard(name="Faculty Qualification", value=88.0, label="Excellent", color="blue"),
            KPICard(name="Student Progression", value=79.2, label="Good", color="blue"),
            KPICard(name="Infrastructure", value=70.5, label="Good", color="orange"),
        ]
        kpis = {"overall_score": 82.1, "research_output": 75.5, "faculty_qualification": 88.0, "student_progression": 79.2, "infrastructure": 70.5}
    else:  # mixed
        mode = "mixed"
        institution_name = "National Institute of Technology Karnataka"
        kpi_cards = [
            KPICard(name="Combined Overall Score", value=80.3, label="Excellent", color="blue"),
            KPICard(name="AICTE Compliance", value=85.0, label="Excellent", color="blue"),
            KPICard(name="UGC Compliance", value=78.2, label="Good", color="blue"),
            KPICard(name="Quality Assurance", value=76.5, label="Good", color="orange"),
            KPICard(name="Governance Score", value=82.0, label="Excellent", color="blue"),
        ]
        kpis = {"overall_score": 80.3, "aicte_compliance": 85.0, "ugc_compliance": 78.2, "quality_assurance": 76.5, "governance": 82.0}
    
    # Sample blocks
    blocks = [
        BlockWithData(
            block_id="demo-block-1",
            block_type="institution_info",
            block_name="Institution Information",
            is_present=True,
            is_outdated=False,
            is_low_quality=False,
            is_invalid=False,
            confidence=0.95,
            extracted_fields_count=12,
            evidence_snippet="Institution Name: " + institution_name,
            evidence_page=1,
            source_doc="Annual Report 2024.pdf",
            data={"name": institution_name, "established": 1963, "type": "Government"}
        ),
        BlockWithData(
            block_id="demo-block-2",
            block_type="faculty_info",
            block_name="Faculty Information",
            is_present=True,
            is_outdated=False,
            is_low_quality=False,
            is_invalid=False,
            confidence=0.92,
            extracted_fields_count=8,
            evidence_snippet="Total Faculty: 450, PhD: 380",
            evidence_page=5,
            source_doc="Faculty Details.pdf",
            data={"total_faculty": 450, "phd_faculty": 380, "regular": 420, "contract": 30}
        ),
        BlockWithData(
            block_id="demo-block-3",
            block_type="student_info",
            block_name="Student Information",
            is_present=True,
            is_outdated=False,
            is_low_quality=False,
            is_invalid=False,
            confidence=0.94,
            extracted_fields_count=10,
            evidence_snippet="Total Students: 5200, UG: 3800, PG: 1400",
            evidence_page=8,
            source_doc="Student Statistics.pdf",
            data={"total_students": 5200, "ug_students": 3800, "pg_students": 1400}
        ),
    ]
    
    block_cards = [BlockCard(**{k: v for k, v in b.model_dump().items() if k != 'data'}) for b in blocks]
    
    # Sufficiency
    sufficiency = SufficiencyCard(
        percentage=85.0,
        present_count=17,
        required_count=20,
        missing_blocks=["detailed_placement_data", "research_publications", "financial_audit"],
        penalty_breakdown={"missing_blocks": 15},
        color="blue"
    )
    
    # Compliance flags
    compliance_flags = [
        ComplianceFlag(
            severity="warning",
            title="Pending Equipment Certification",
            reason="Lab equipment certification expired in March 2024",
            evidence_page=None,
            evidence_snippet=None,
            recommendation="Renew equipment certification before next inspection"
        ),
        ComplianceFlag(
            severity="info",
            title="Faculty Training Update",
            reason="15 faculty members completed mandatory training",
            evidence_page=None,
            evidence_snippet=None,
            recommendation="Continue training program for remaining faculty"
        ),
    ]
    
    return DashboardResponse(
        batch_id=batch_id,
        mode=mode,
        institution_name=institution_name,
        kpi_cards=kpi_cards,
        kpis=kpis,
        block_cards=block_cards,
        blocks=blocks,
        sufficiency=sufficiency,
        compliance_flags=compliance_flags,
        trend_data=[],
        total_documents=5,
        processed_documents=5,
        approval_classification=ApprovalClassification(
            category=mode.upper(),
            subtype="Regular Approval",
            signals=["All documents verified", "KPIs within acceptable range"]
        ),
        approval_readiness=ApprovalReadiness(
            approval_category=mode.upper(),
            approval_readiness_score=85.0,
            present=17,
            required=20,
            approval_missing_documents=["Detailed placement data", "Research publications"],
            recommendation="Ready for approval with minor documentation updates"
        ),
        batch_status="completed",
        overall_score=kpis.get("overall_score"),
        is_invalid=False,
        invalid_reason=None
    )


@router.get("/evaluations", response_model=List[dict])
def list_evaluations(
    academic_year: Optional[str] = None,
    mode: Optional[str] = None,
    department_name: Optional[str] = None,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    List available evaluations (batches) for dashboard selector.
    PLATFORM MODEL: Returns stored evaluations filtered by year, mode, department.
    Only returns completed, valid batches.
    """
    db = get_db()
    
    try:
        query = db.query(Batch).filter(
            Batch.status == "completed",
            Batch.is_invalid == 0  # Only valid batches
        )
        
        # PLATFORM MODEL: Role-based filtering
        if user:
            user_id = user.get("uid")
            role = user.get("role", "department")
            
            if role == "institution":
                # Institution users can see all batches
                pass
            else:
                # Department users see only their department's batches
                department_id = user.get("department_id")
                if department_id:
                    query = query.filter(Batch.department_id == department_id)
                elif user_id:
                    query = query.filter(Batch.user_id == user_id)
        
        # Apply filters
        if academic_year:
            query = query.filter(Batch.academic_year == academic_year)
        if mode:
            query = query.filter(Batch.mode == mode)
        if department_name:
            query = query.filter(Batch.department_name == department_name)
        
        batches = query.order_by(Batch.academic_year.desc(), Batch.created_at.desc()).all()
        
        # Format response
        evaluations = []
        for batch in batches:
            from config.database import File
            file_count = db.query(File).filter(File.batch_id == batch.id).count()
            
            evaluations.append({
                "batch_id": batch.id,
                "academic_year": batch.academic_year,
                "mode": batch.mode,
                "institution_name": batch.institution_name,
                "department_name": batch.department_name,
                "overall_score": batch.kpi_results.get("overall_score", {}).get("value") if batch.kpi_results else None,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "total_documents": file_count
            })
        
        return evaluations
    
    finally:
        close_db(db)


@router.get("/kpi-details/{batch_id}", response_model=KPIDetailsResponse)
def get_kpi_details_endpoint(
    batch_id: str,
    kpi_type: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """Get detailed KPI breakdown for a batch."""
    # DEMO MODE: Return demo KPI details for demo batches
    if batch_id.startswith("demo-"):
        from schemas.kpi_details import ParameterBreakdown, FormulaStep, KPIBreakdown
        
        # Create realistic demo breakdowns
        demo_fsr = KPIBreakdown(
            kpi_key="fsr_score",
            kpi_name="Faculty-Student Ratio Score",
            final_score=85.2,
            parameters=[
                ParameterBreakdown(parameter_name="total_faculty", display_name="Total Faculty", raw_value=450, normalized_value=450.0, unit="persons", weight=1.0, missing=False),
                ParameterBreakdown(parameter_name="total_students", display_name="Total Students", raw_value=5200, normalized_value=5200.0, unit="persons", weight=1.0, missing=False),
            ],
            formula_steps=[
                FormulaStep(step_number=1, description="Calculate student-faculty ratio", formula="ratio = total_students / total_faculty", result=11.56),
                FormulaStep(step_number=2, description="Compare with ideal ratio (15:1 for AICTE)", formula="score = 100 (ratio ≤ 15 is excellent)", result=85.2),
            ],
            formula_text="fsr_score = min(100, max(0, (ideal_ratio / actual_ratio) * 100))",
            missing_parameters=[],
            data_quality="complete",
            confidence=1.0
        )
        
        demo_infra = KPIBreakdown(
            kpi_key="infrastructure_score",
            kpi_name="Infrastructure Score",
            final_score=72.0,
            parameters=[
                ParameterBreakdown(parameter_name="built_up_area", display_name="Built-up Area", raw_value="85000 sqft", normalized_value=7897.0, unit="sqm", weight=0.40, score=78.97, contribution=31.59, missing=False),
                ParameterBreakdown(parameter_name="classrooms", display_name="Classrooms", raw_value=45, normalized_value=45.0, unit="count", weight=0.25, score=100.0, contribution=25.0, missing=False),
                ParameterBreakdown(parameter_name="library_area", display_name="Library Area", raw_value="4500 sqft", normalized_value=418.0, unit="sqm", weight=0.15, score=83.6, contribution=12.54, missing=False),
                ParameterBreakdown(parameter_name="lab_area", display_name="Lab Area", raw_value="8000 sqft", normalized_value=743.0, unit="sqm", weight=0.10, score=74.3, contribution=7.43, missing=False),
                ParameterBreakdown(parameter_name="digital_resources", display_name="Digital Resources", raw_value="Yes", normalized_value=1.0, unit="", weight=0.10, score=100.0, contribution=10.0, missing=False),
            ],
            formula_steps=[
                FormulaStep(step_number=1, description="Calculate Built-up Area contribution", formula="contribution = (value / norm) * 40%", result=31.59),
                FormulaStep(step_number=2, description="Calculate Classrooms contribution", formula="contribution = (value / norm) * 25%", result=25.0),
                FormulaStep(step_number=3, description="Calculate Library Area contribution", formula="contribution = (value / norm) * 15%", result=12.54),
                FormulaStep(step_number=4, description="Calculate Lab Area contribution", formula="contribution = (value / norm) * 10%", result=7.43),
                FormulaStep(step_number=5, description="Calculate Digital Resources contribution", formula="contribution = (value / norm) * 10%", result=10.0),
                FormulaStep(step_number=6, description="Sum all contributions", formula="infrastructure_score = sum(contributions)", result=72.0),
            ],
            formula_text="infrastructure_score = Σ(component_score × weight)",
            missing_parameters=[],
            data_quality="complete",
            confidence=1.0
        )
        
        demo_placement = KPIBreakdown(
            kpi_key="placement_index",
            kpi_name="Placement Index",
            final_score=92.3,
            parameters=[
                ParameterBreakdown(parameter_name="placed_students", display_name="Students Placed", raw_value=780, normalized_value=780.0, unit="count", weight=0.0, missing=False),
                ParameterBreakdown(parameter_name="eligible_students", display_name="Eligible Students", raw_value=850, normalized_value=850.0, unit="count", weight=0.0, missing=False),
                ParameterBreakdown(parameter_name="placement_rate", display_name="Placement Rate", raw_value=91.76, normalized_value=91.76, unit="%", weight=0.60, score=91.76, contribution=55.06, missing=False),
                ParameterBreakdown(parameter_name="average_package", display_name="Average Package", raw_value=8.5, normalized_value=8.5, unit="LPA", weight=0.25, score=85.0, contribution=21.25, missing=False),
                ParameterBreakdown(parameter_name="highest_package", display_name="Highest Package", raw_value=42.0, normalized_value=42.0, unit="LPA", weight=0.15, score=100.0, contribution=15.0, missing=False),
            ],
            formula_steps=[
                FormulaStep(step_number=1, description="Placement rate contribution (60% weight)", formula="rate_contribution = min(100, placement_rate) × 0.6", result=55.06),
                FormulaStep(step_number=2, description="Average package contribution (25% weight, 10 LPA = 100)", formula="avg_pkg_contribution = min(100, (avg_package / 10) × 100) × 0.25", result=21.25),
                FormulaStep(step_number=3, description="Highest package contribution (15% weight, 20 LPA = 100)", formula="high_pkg_contribution = min(100, (highest_package / 20) × 100) × 0.15", result=15.0),
                FormulaStep(step_number=4, description="Sum all contributions", formula="placement_index = rate_contrib + avg_pkg_contrib + high_pkg_contrib", result=92.3),
            ],
            formula_text="placement_index = (placement_rate × 0.6) + (avg_package_score × 0.25) + (highest_package_score × 0.15)",
            missing_parameters=[],
            data_quality="complete",
            confidence=0.9
        )
        
        demo_lab = KPIBreakdown(
            kpi_key="lab_compliance_index",
            kpi_name="Lab Compliance Index",
            final_score=68.5,
            parameters=[
                ParameterBreakdown(parameter_name="computer_labs", display_name="Computer Labs", raw_value=8, normalized_value=8.0, unit="count", weight=0.30, score=100.0, contribution=30.0, missing=False),
                ParameterBreakdown(parameter_name="science_labs", display_name="Science Labs", raw_value=4, normalized_value=4.0, unit="count", weight=0.25, score=100.0, contribution=25.0, missing=False),
                ParameterBreakdown(parameter_name="engineering_labs", display_name="Engineering Labs", raw_value=5, normalized_value=5.0, unit="count", weight=0.25, score=83.3, contribution=20.83, missing=False),
                ParameterBreakdown(parameter_name="lab_equipment", display_name="Lab Equipment Status", raw_value="Operational", normalized_value=1.0, unit="status", weight=0.20, score=100.0, contribution=20.0, missing=False),
            ],
            formula_steps=[
                FormulaStep(step_number=1, description="Calculate Computer Labs contribution", formula="contribution = (count / 5) × 30%", result=30.0),
                FormulaStep(step_number=2, description="Calculate Science Labs contribution", formula="contribution = (count / 4) × 25%", result=25.0),
                FormulaStep(step_number=3, description="Calculate Engineering Labs contribution", formula="contribution = (count / 6) × 25%", result=20.83),
                FormulaStep(step_number=4, description="Calculate Lab Equipment Status contribution", formula="contribution = status × 20%", result=20.0),
                FormulaStep(step_number=5, description="Sum all contributions", formula="lab_compliance_index = sum(contributions)", result=68.5),
            ],
            formula_text="lab_compliance_index = Σ(component_score × weight)",
            missing_parameters=[],
            data_quality="complete",
            confidence=1.0
        )
        
        demo_overall = KPIBreakdown(
            kpi_key="overall_score",
            kpi_name="Overall Score",
            final_score=78.5,
            parameters=[
                ParameterBreakdown(parameter_name="fsr_score", display_name="FSR Score", raw_value=85.2, normalized_value=85.2, unit="score", weight=0.25, score=85.2, contribution=21.3, missing=False),
                ParameterBreakdown(parameter_name="infrastructure_score", display_name="Infrastructure Score", raw_value=72.0, normalized_value=72.0, unit="score", weight=0.25, score=72.0, contribution=18.0, missing=False),
                ParameterBreakdown(parameter_name="placement_index", display_name="Placement Index", raw_value=92.3, normalized_value=92.3, unit="score", weight=0.30, score=92.3, contribution=27.69, missing=False),
                ParameterBreakdown(parameter_name="lab_compliance_index", display_name="Lab Compliance Index", raw_value=68.5, normalized_value=68.5, unit="score", weight=0.20, score=68.5, contribution=13.7, missing=False),
            ],
            formula_steps=[
                FormulaStep(step_number=1, description="FSR Score contribution (25% weight)", formula="contribution = 85.2 × 0.25", result=21.3),
                FormulaStep(step_number=2, description="Infrastructure Score contribution (25% weight)", formula="contribution = 72.0 × 0.25", result=18.0),
                FormulaStep(step_number=3, description="Placement Index contribution (30% weight)", formula="contribution = 92.3 × 0.30", result=27.69),
                FormulaStep(step_number=4, description="Lab Compliance Index contribution (20% weight)", formula="contribution = 68.5 × 0.20", result=13.7),
                FormulaStep(step_number=5, description="Sum all KPI contributions", formula="overall_score = Σ(kpi_score × weight)", result=78.5),
            ],
            formula_text="overall_score = (FSR × 0.25) + (Infrastructure × 0.25) + (Placement × 0.30) + (Lab × 0.20)",
            missing_parameters=[],
            data_quality="complete",
            confidence=0.95
        )
        
        return KPIDetailsResponse(
            batch_id=batch_id,
            institution_name="Indian Institute of Technology Delhi" if "aicte" in batch_id else "Delhi University - North Campus",
            mode="aicte" if "aicte" in batch_id else "ugc",
            fsr=demo_fsr,
            infrastructure=demo_infra,
            placement=demo_placement,
            lab_compliance=demo_lab,
            overall=demo_overall
        )
    
    from services.kpi_details import get_kpi_details
    
    # PLATFORM MODEL: Enforce user access control
    db = get_db()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        
        # SYSTEM BATCHES: Allow access to everyone (demo/comparison data)
        is_system_batch = getattr(batch, 'data_source', 'user') == 'system'
        
        if user and not is_system_batch:
            user_id = user.get("uid")
            role = user.get("role", "department")
            
            if role != "institution":
                department_id = user.get("department_id")
                if department_id:
                    if batch.department_id != department_id:
                        raise HTTPException(status_code=403, detail="Access denied")
                elif user_id:
                    if batch.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Access denied")
        
        
        # NOTE: Removed is_invalid blocking - allow users to see whatever KPI data is available
        # The frontend should handle incomplete data gracefully
        # Previously: if batch.is_invalid == 1: raise HTTPException(400, "Cannot get KPI details for invalid batch")
        
        return get_kpi_details(batch_id, kpi_type)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        close_db(db)


@router.get("/trends/{batch_id}")
def get_yearwise_trends(
    batch_id: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Get year-wise KPI trends for a batch.
    Department-wise: If institution_name and department_name are set, 
    includes historical data from same institution+department.
    Requires minimum 3 years for valid trends.
    """
    # DEMO MODE: Return demo trends data for demo batches
    if batch_id.startswith("demo-"):
        return {
            "years_available": [2022, 2023, 2024],
            "kpis_per_year": {
                "2022": {"fsr_score": 72.5, "infrastructure_score": 65.0, "placement_index": 78.0, "overall_score": 71.8},
                "2023": {"fsr_score": 78.2, "infrastructure_score": 68.5, "placement_index": 82.0, "overall_score": 76.2},
                "2024": {"fsr_score": 85.2, "infrastructure_score": 72.0, "placement_index": 92.3, "overall_score": 78.5}
            },
            "trends": {
                "fsr_score": {"slope": 6.35, "volatility": 0.12, "min": 72.5, "max": 85.2, "avg": 78.6, "insight": "Improving steadily", "data_points": 3},
                "infrastructure_score": {"slope": 3.5, "volatility": 0.08, "min": 65.0, "max": 72.0, "avg": 68.5, "insight": "Gradual improvement", "data_points": 3},
                "placement_index": {"slope": 7.15, "volatility": 0.15, "min": 78.0, "max": 92.3, "avg": 84.1, "insight": "Strong growth", "data_points": 3},
                "overall_score": {"slope": 3.35, "volatility": 0.06, "min": 71.8, "max": 78.5, "avg": 75.5, "insight": "Consistent improvement", "data_points": 3}
            },
            "has_historical_data": True
        }
    
    from services.yearwise_kpi import process_yearwise_kpis
    
    db = get_db()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        
        # SYSTEM BATCHES: Allow access to everyone (demo/comparison data)
        is_system_batch = getattr(batch, 'data_source', 'user') == 'system'
        
        # PLATFORM MODEL: Enforce user access control (skip for system batches)
        if user and not is_system_batch:
            user_id = user.get("uid")
            role = user.get("role", "department")
            
            if role != "institution":
                department_id = user.get("department_id")
                if department_id:
                    if batch.department_id != department_id:
                        raise HTTPException(status_code=403, detail="Access denied")
                elif user_id:
                    if batch.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if batch is invalid - return graceful response instead of error
        if batch.is_invalid == 1:
            return {
                "has_historical_data": False,
                "insufficient_data": True,
                "insufficient_data_reason": "Batch marked as invalid due to insufficient extracted data. Please upload documents with complete institutional information.",
                "years_available": [],
                "kpis_per_year": {},
                "trends": {}
            }
        
        # Get blocks from current batch
        blocks = db.query(Block).filter(Block.batch_id == batch_id).all()
        block_list = [{"data": b.data or {}} for b in blocks]
        
        # PRODUCTION HARDENING: Use production guard for strict data contract
        from services.production_guard import ProductionGuard
        
        # If department-wise data available, include historical batches
        if batch.institution_name and batch.department_name:
            # Find historical batches from same institution + department
            historical_batches = db.query(Batch).filter(
                Batch.institution_name == batch.institution_name,
                Batch.department_name == batch.department_name,
                Batch.id != batch_id,  # Exclude current batch
                Batch.is_invalid == 0,  # Only valid batches
                Batch.status == "completed"  # Only completed batches
            ).order_by(Batch.academic_year).all()
            
            # Validate data contract: same institution, same department, 3+ years
            all_batches = [batch] + historical_batches
            is_valid, error_msg, valid_batches = ProductionGuard.validate_trends_data_contract(
                all_batches,
                batch.institution_name,
                batch.department_name
            )
            
            if not is_valid:
                return {
                    "has_historical_data": False,
                    "insufficient_data": True,
                    "insufficient_data_reason": error_msg,
                    "years_available": [],
                    "kpi_trends": {}
                }
            
            # Add blocks from historical batches
            for hist_batch in historical_batches:
                hist_blocks = db.query(Block).filter(Block.batch_id == hist_batch.id).all()
                block_list.extend([{"data": b.data or {}} for b in hist_blocks])
        
        # Process year-wise KPIs
        trend_results = process_yearwise_kpis(block_list, batch.mode)
        
        return trend_results
    
    finally:
        close_db(db)


@router.get("/forecast/{batch_id}/{kpi_name}")
def get_forecast(
    batch_id: str,
    kpi_name: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Get forecast for a specific KPI.
    Requires minimum 3 years of historical data.
    """
    # DEMO MODE: Return demo forecast data for demo batches
    if batch_id.startswith("demo-"):
        return {
            "has_forecast": True,
            "can_forecast": True,
            "insufficient_data": False,
            "forecast": [
                {"year": 2025, "predicted_value": 82.5, "lower_bound": 78.0, "upper_bound": 87.0, "confidence": 0.85},
                {"year": 2026, "predicted_value": 85.5, "lower_bound": 80.0, "upper_bound": 91.0, "confidence": 0.75},
                {"year": 2027, "predicted_value": 88.5, "lower_bound": 82.0, "upper_bound": 95.0, "confidence": 0.65}
            ],
            "confidence_band": 0.9,
            "explanation": f"Based on 3 years of historical data, {kpi_name} is projected to increase steadily.",
            "model_info": {
                "method": "linear_regression",
                "slope": 3.5,
                "intercept": 65.0,
                "r_squared": 0.92,
                "historical_points": 3
            }
        }
    
    from services.forecast_service import ForecastService
    
    db = get_db()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        
        # SYSTEM BATCHES: Allow access to everyone (demo/comparison data)
        is_system_batch = getattr(batch, 'data_source', 'user') == 'system'
        
        # PLATFORM MODEL: Enforce user access control (skip for system batches)
        if user and not is_system_batch:
            user_id = user.get("uid")
            role = user.get("role", "department")
            
            if role != "institution":
                department_id = user.get("department_id")
                if department_id:
                    if batch.department_id != department_id:
                        raise HTTPException(status_code=403, detail="Access denied")
                elif user_id:
                    if batch.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Access denied")
        
        # NOTE: Return graceful response for invalid batches instead of blocking
        # Previously: if batch.is_invalid == 1: raise HTTPException(400, "Cannot generate forecast")
        if batch.is_invalid == 1:
            return {
                "has_forecast": False,
                "insufficient_data": True,
                "insufficient_data_reason": "Batch marked as invalid due to insufficient data",
                "forecast": None
            }
        
        # Get historical batches for same department
        if not batch.institution_name or not batch.department_name:
            return {
                "has_forecast": False,
                "insufficient_data": True,
                "insufficient_data_reason": "Batch missing institution_name or department_name",
                "forecast": None
            }
        
        historical_batches = db.query(Batch).filter(
            Batch.institution_name == batch.institution_name,
            Batch.department_name == batch.department_name,
            Batch.is_invalid == 0,  # Only valid batches
            Batch.status == "completed"
        ).order_by(Batch.academic_year).all()
        
        # Validate data contract
        from services.production_guard import ProductionGuard
        all_batches = [batch] + [b for b in historical_batches if b.id != batch_id]
        is_valid, error_msg, valid_batches = ProductionGuard.validate_trends_data_contract(
            all_batches,
            batch.institution_name,
            batch.department_name
        )
        
        if not is_valid:
            return {
                "has_forecast": False,
                "insufficient_data": True,
                "insufficient_data_reason": error_msg,
                "forecast": None
            }
        
        # Generate forecast
        forecast_service = ForecastService()
        forecast_result = forecast_service.forecast_kpi(
            valid_batches,
            kpi_name,
            batch.mode
        )
        
        return forecast_result
    
    finally:
        close_db(db)


@router.get("/{batch_id}", response_model=DashboardResponse)
def get_dashboard_data(
    batch_id: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Get complete dashboard data for a batch
    PERFORMANCE: Cached for 5 minutes
    """
    # DEMO MODE: Return demo data for demo batch IDs
    if batch_id.startswith("demo-"):
        return _get_demo_dashboard_data(batch_id)
    
    # PERFORMANCE: Check cache first
    from utils.performance_cache import cache, get_cache_key
    import logging
    logger = logging.getLogger(__name__)
    
    cache_key = get_cache_key("dashboard", batch_id)
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f"Cache hit for dashboard {batch_id}")
        return cached
    
    db = get_db()
    
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        
        # SYSTEM BATCHES: Allow access to everyone (demo/comparison data)
        is_system_batch = getattr(batch, 'data_source', 'user') == 'system'
        
        # PLATFORM MODEL: Enforce user access control (skip for system batches)
        if user and not is_system_batch:
            user_id = user.get("uid")
            role = user.get("role", "department")
            
            # Institution users can access all batches
            if role != "institution":
                # Department users can only access their own department's batches
                department_id = user.get("department_id")
                if department_id:
                    if batch.department_id != department_id:
                        raise HTTPException(status_code=403, detail="Access denied: You can only access your department's batches")
                elif user_id:
                    if batch.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Access denied: You can only access your own batches")
        
        # NOTE: Invalid batches are now allowed to be displayed with a warning
        # The frontend should show a banner explaining the data is incomplete
        is_batch_invalid = batch.is_invalid == 1
        
        # Get KPI cards

        kpi_results = batch.kpi_results or {}
        kpi_cards = []
        kpis_map = {}
        if kpi_results and isinstance(kpi_results, dict):
            for kpi_id, kpi_data in kpi_results.items():
                # Handle both formats: nested dict {value: X} and direct numeric X
                if isinstance(kpi_data, dict) and "value" in kpi_data:
                    value = kpi_data.get("value", 0)
                    name = kpi_data.get("name", kpi_id.replace("_", " ").title())
                elif isinstance(kpi_data, (int, float)):
                    # Direct numeric value (from system batches)
                    value = kpi_data
                    name = kpi_id.replace("_", " ").title()
                else:
                    # Skip invalid formats
                    continue
                
                # Handle None values - display as "Insufficient Data"
                if value is None:
                    kpi_cards.append(KPICard(
                        name=name,
                        value=None,
                        label="Insufficient Data",
                        color="gray"
                    ))
                else:
                    kpi_cards.append(KPICard(
                        name=name,
                        value=float(value),
                        label=name,
                        color="blue" if value >= 70 else "orange" if value >= 50 else "red"
                    ))
                # also populate simplified map
                kpis_map[kpi_id] = value if value is None else float(value)
    
        # Get sufficiency
        sufficiency_result = batch.sufficiency_result or {}
        if not sufficiency_result:
            # Calculate on-the-fly if not stored
            from services.block_sufficiency import BlockSufficiencyService
            blocks = db.query(Block).filter(Block.batch_id == batch_id).all()
            block_list = [{
                "block_type": b.block_type,
                "extracted_data": b.data or {},
                "is_outdated": bool(b.is_outdated),
                "is_low_quality": bool(b.is_low_quality),
                "is_invalid": bool(b.is_invalid)
            } for b in blocks]
            sufficiency_service = BlockSufficiencyService()
            sufficiency_result = sufficiency_service.calculate_sufficiency(batch.mode, block_list)
        
        sufficiency = SufficiencyCard(
            percentage=sufficiency_result.get("percentage", 0),
            present_count=sufficiency_result.get("present_count", 0),
            required_count=sufficiency_result.get("required_count", 10),
            missing_blocks=sufficiency_result.get("missing_blocks", []),
            penalty_breakdown=sufficiency_result.get("penalty_breakdown", {}),
            color=sufficiency_result.get("color", "red")
        )
    
        # Get information blocks
        blocks = db.query(Block).filter(Block.batch_id == batch_id).all()
        
        # Group blocks by type
        blocks_by_type = {}
        for block in blocks:
            block_type = block.block_type
            if block_type:
                if block_type not in blocks_by_type:
                    blocks_by_type[block_type] = []
                blocks_by_type[block_type].append(block)
        
        # Create block cards for all required blocks (mode-specific)
        new_university = bool(batch.new_university) if batch.new_university else False
        required_blocks = get_information_blocks(batch.mode, new_university)  # Get mode-specific blocks
        block_cards = []
        blocks_with_data: list[BlockWithData] = []
        for block_type in required_blocks:
            block_list = blocks_by_type.get(block_type, [])
            block_desc = get_block_description(block_type)
            
            # Find best block (highest confidence, not invalid)
            best_block = None
            if block_list:
                valid_blocks = [b for b in block_list if not b.is_invalid]
                if valid_blocks:
                    best_block = max(valid_blocks, key=lambda b: b.extraction_confidence)
                else:
                    best_block = max(block_list, key=lambda b: b.extraction_confidence)
            
            if best_block:
                card = BlockCard(
                    block_id=best_block.id,
                    block_type=block_type,
                    block_name=block_desc.get("name", block_type.replace("_", " ").title()),
                    is_present=True,
                    is_outdated=bool(best_block.is_outdated),
                    is_low_quality=bool(best_block.is_low_quality),
                    is_invalid=bool(best_block.is_invalid),
                    confidence=best_block.extraction_confidence,
                    extracted_fields_count=len(best_block.data or {}),
                    evidence_snippet=best_block.evidence_snippet,
                    evidence_page=best_block.evidence_page,
                    source_doc=best_block.source_doc
                )
                block_cards.append(card)
                blocks_with_data.append(BlockWithData(**card.model_dump(), data=best_block.data or {}))
            else:
                # Missing block
                card = BlockCard(
                    block_id="",
                    block_type=block_type,
                    block_name=block_desc.get("name", block_type.replace("_", " ").title()),
                    is_present=False,
                    is_outdated=False,
                    is_low_quality=False,
                    is_invalid=False,
                    confidence=0.0,
                    extracted_fields_count=0
                )
                block_cards.append(card)
                blocks_with_data.append(BlockWithData(**card.model_dump(), data={}))
        
        # Get compliance flags
        compliance_flags_db = db.query(ComplianceFlagModel).filter(ComplianceFlagModel.batch_id == batch_id).all()
        compliance_flags = [
            ComplianceFlag(
                severity=flag.severity,
                title=flag.title,
                reason=flag.reason,
                evidence_page=None,
                evidence_snippet=None,
                recommendation=flag.recommendation
            )
            for flag in compliance_flags_db
        ]
        
        # Get trend data
        trend_results = batch.trend_results or {}
        trend_data = []
        if trend_results.get("has_trend_data"):
            trend_data = [
                TrendDataPoint(
                    year=point.get("year", ""),
                    kpi_name=point.get("kpi_name", ""),
                    value=point.get("value", 0)
                )
                for point in trend_results.get("trend_data", [])
            ]
        
        # Get file count
        from config.database import File
        file_count = db.query(File).filter(File.batch_id == batch_id).count()

        # Convert dict to Pydantic models if present
        approval_classification = None
        if batch.approval_classification:
            if isinstance(batch.approval_classification, dict):
                try:
                    approval_classification = ApprovalClassification(
                        category=batch.approval_classification.get("category", "unknown"),
                        subtype=batch.approval_classification.get("subtype", "unknown"),
                        signals=batch.approval_classification.get("signals", []) if isinstance(batch.approval_classification.get("signals"), list) else []
                    )
                except Exception as e:
                    logger.warning(f"Error converting approval_classification: {e}")
                    approval_classification = None
        
        approval_readiness = None
        if batch.approval_readiness:
            if isinstance(batch.approval_readiness, dict):
                try:
                    classification_dict = batch.approval_readiness.get("classification", {})
                    if not isinstance(classification_dict, dict):
                        classification_dict = {}
                    
                    approval_readiness = ApprovalReadiness(
                        approval_category=classification_dict.get("category", batch.mode or "aicte"),
                        approval_readiness_score=batch.approval_readiness.get("readiness_score", 0.0),
                        present=batch.approval_readiness.get("present_documents", 0),
                        required=batch.approval_readiness.get("required_documents", 0),
                        approval_missing_documents=batch.approval_readiness.get("missing_documents", []) if isinstance(batch.approval_readiness.get("missing_documents"), list) else [],
                        recommendation="Ready" if batch.approval_readiness.get("readiness_score", 0) >= 80 else "Needs improvement"
                    )
                except Exception as e:
                    logger.warning(f"Error converting approval_readiness: {e}")
                    approval_readiness = None
        
        result = DashboardResponse(
            batch_id=batch_id,
            mode=batch.mode,
            institution_name=batch.institution_name,
            kpi_cards=kpi_cards,
            kpis=kpis_map,
            block_cards=block_cards,
            blocks=blocks_with_data,
            sufficiency=sufficiency,
            compliance_flags=compliance_flags,
            trend_data=trend_data,
            total_documents=file_count,
            processed_documents=file_count if batch.status == "completed" else 0,
            approval_classification=approval_classification,
            approval_readiness=approval_readiness,
            batch_status=batch.status,
            overall_score=kpis_map.get("overall_score"),
            is_invalid=is_batch_invalid,
            invalid_reason="Insufficient data extracted from documents. The AI could not find enough required information." if is_batch_invalid else None
        )

        
        # PERFORMANCE: Cache result
        cache.set(cache_key, result)
        return result
    finally:
        close_db(db)
