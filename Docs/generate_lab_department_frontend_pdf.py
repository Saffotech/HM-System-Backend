"""Generator: Frontend guide for Lab Laboratory vs Radiology department implementation."""
from pathlib import Path

from fpdf import FPDF

OUT = (
    Path(__file__).resolve().parent
    / "frontend-lab-department-implementation.pdf"
)


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Lab Department Implementation (Frontend Guide)",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(1)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 8, title)
        self.ln(1)

    def sub_title(self, title: str):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 7, title)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5.5, text)
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5.5, f"  - {text}")

    def callout(self, label: str, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(140, 60, 20)
        self.multi_cell(self.epw, 6, label)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.epw, 5.5, text)
        self.ln(1)

    def code_block(self, text: str):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        for line in text.strip("\n").splitlines():
            safe = line.encode("latin-1", "replace").decode("latin-1")
            self.set_x(self.l_margin)
            self.cell(
                self.epw,
                4.5,
                "  " + safe[:105],
                new_x="LMARGIN",
                new_y="NEXT",
                fill=True,
            )
        self.ln(2)

    def table_row(
        self,
        cols: list[str],
        bold: bool = False,
        widths: list[float] | None = None,
    ):
        if widths is None:
            widths = [self.epw / len(cols)] * len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        y0 = self.get_y()
        x0 = self.l_margin
        # Single-line cells for simplicity
        for i, col in enumerate(cols):
            self.set_xy(x0 + sum(widths[:i]), y0)
            self.cell(widths[i], 6, col[:55], border=1)
        self.ln()


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Cover
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 60, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 10, "Lab Department Implementation")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, "Frontend Developer Guide")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.body(
        "Date: 11 August 2026  |  Audience: Frontend developers  |  "
        "Scope: Laboratory vs Radiology departments for lab orders and lab technicians."
    )
    pdf.callout(
        "IMPORTANT",
        "Backend for department routing is ALREADY DONE. This document describes "
        "frontend-only updates. Do not change backend files for this feature.",
    )

    # 1. Goal
    pdf.section_title("1. Product Goal")
    pdf.body(
        "The Lab module has two departments. Lab technicians belong to one department "
        "and only see orders for that department. Doctors choose the lab department "
        "when ordering a test, then only see tests for that department."
    )
    w = [pdf.epw * 0.28, pdf.epw * 0.36, pdf.epw * 0.36]
    pdf.table_row(["Department", "Code", "Example tests"], bold=True, widths=w)
    pdf.table_row(
        ["Laboratory (Pathology)", "LAB", "Blood, Urine, CBC, Biochemistry"],
        widths=w,
    )
    pdf.table_row(
        ["Radiology (Imaging)", "RAD", "X-Ray, USG, CT, MRI, Mammography"],
        widths=w,
    )
    pdf.ln(2)
    pdf.sub_title("Where Laboratory / Radiology MUST appear")
    pdf.bullet("Doctor module - when creating a lab order (department picker + filtered tests)")
    pdf.bullet("Admin / Super-admin - when creating or editing a lab technician (assign LAB or RAD)")
    pdf.sub_title("Where Laboratory must NOT appear")
    pdf.bullet(
        "OPD Billing / Register Patient / Book Appointment - clinical doctor department dropdown"
    )
    pdf.bullet(
        "That dropdown is for Cardiology, Pediatrics, etc. Lab departments are not visit departments."
    )

    # 2. End-to-end flow
    pdf.section_title("2. End-to-End Flow")
    pdf.sub_title("A. Admin assigns lab tech department")
    pdf.bullet("Create or edit staff with role lab_technician")
    pdf.bullet("Require department: Laboratory (LAB) or Radiology (RAD) only")
    pdf.bullet("POST /register or PATCH staff update with department_id")
    pdf.sub_title("B. Doctor orders a lab test")
    pdf.bullet("Open consultation / Labs section")
    pdf.bullet("Select Lab Department: Laboratory OR Radiology")
    pdf.bullet("Test dropdown shows only that department's tests")
    pdf.bullet("POST /lab-tests with department_id (+ test_name, category, priority, ...)")
    pdf.sub_title("C. Lab tech login")
    pdf.bullet("Same login as today; role remains lab_technician")
    pdf.bullet("GET /lab/orders, /lab/dashboard, /lab/reports are auto-filtered by backend")
    pdf.bullet("Tech with no department_id gets HTTP 403 until admin assigns LAB/RAD")

    # 3. Backend contract (read-only for FE)
    pdf.add_page()
    pdf.section_title("3. Backend Contract (Already Implemented)")
    pdf.body(
        "Frontend must send and display department_id. Backend enforces scoping."
    )
    pdf.sub_title("3.1 Create lab order - POST /lab-tests")
    pdf.code_block(
        """
{
  "appointment_id": 123,
  "test_name": "CBC",
  "category": "Blood",
  "department_id": 11,
  "priority": "Normal",
  "clinical_notes": "optional"
}
"""
    )
    pdf.bullet("department_id is optional for backward compatibility")
    pdf.bullet(
        "If omitted, backend INFERS: Radiology-like category/test_name -> RAD, else -> LAB"
    )
    pdf.bullet("Prefer ALWAYS sending department_id from the new doctor UI")
    pdf.sub_title("3.2 Lab order responses")
    pdf.bullet("LabTestResponse / list items include department_id")
    pdf.bullet("Lab technician order list/detail also include department_id")
    pdf.sub_title("3.3 Lab technician APIs (auto-scoped)")
    pdf.bullet("GET /lab/dashboard")
    pdf.bullet("GET /lab/orders and GET /lab/orders/{id}")
    pdf.bullet("GET /lab/reports and report detail/file")
    pdf.bullet("PATCH sample-collected / complete, POST report / upload-file")
    pdf.bullet("All filtered or blocked by current_user.department_id")
    pdf.sub_title("3.4 Staff register / update")
    pdf.bullet("Lab technician may store department_id (must be LAB or RAD code)")
    pdf.bullet("Doctor still uses any clinical department")
    pdf.bullet("OPD nurse etc. still do not use department_id on user")

    # 4. Frontend file checklist
    pdf.section_title("4. Frontend Files To Update")
    pdf.callout("NO BACKEND CHANGES", "Update only HM-frontend-Side files listed below.")

    pdf.sub_title("4.1 Hide LAB from OPD clinical department dropdown")
    w2 = [pdf.epw * 0.62, pdf.epw * 0.38]
    pdf.table_row(["File", "What to do"], bold=True, widths=w2)
    pdf.table_row(
        ["src/shared/api/services/opdReference.js", "Filter out code LAB (and RAD if needed)"],
        widths=w2,
    )
    pdf.body(
        "Best place: listDepartments(). Filter departments where code is LAB "
        "(and optionally RAD) so Register Patient, OPD Bill, Book Appointment, etc. "
        "all stop showing Laboratory without editing every page."
    )
    pdf.code_block(
        """
// Example in listDepartments
const LAB_ONLY_CODES = new Set(['LAB']); // or ['LAB','RAD']
return rows
  .map(apiToUiDepartment)
  .filter(Boolean)
  .filter((d) => !LAB_ONLY_CODES.has(String(d.code || '').toUpperCase()));
"""
    )

    pdf.sub_title("4.2 Doctor lab order UI")
    pdf.table_row(["File", "What to do"], bold=True, widths=w2)
    pdf.table_row(
        ["src/features/doctor/constants.js", "Add LAB/RAD departments + tests per dept"],
        widths=w2,
    )
    pdf.table_row(
        [".../doctor/components/ConsultationModal.jsx", "Dept select -> filter tests"],
        widths=w2,
    )
    pdf.table_row(
        [".../doctor/components/LabsSection.jsx", "Same for create/edit lab order"],
        widths=w2,
    )
    pdf.table_row(
        ["src/shared/api/mappers/clinicalMapper.js", "Send department_id in create/update"],
        widths=w2,
    )
    pdf.table_row(
        ["src/shared/api/services/doctorLabs.js", "Only if payload wiring needs tweak"],
        widths=w2,
    )

    pdf.sub_title("4.3 Admin assign department to lab tech")
    pdf.table_row(["File", "What to do"], bold=True, widths=w2)
    pdf.table_row(
        ["features/admin/pages/StaffRegisterPage.jsx", "Dept required for lab_technician"],
        widths=w2,
    )
    pdf.table_row(
        ["features/admin/pages/StaffDetailPage.jsx", "roleRequiresDepartment + LAB/RAD only"],
        widths=w2,
    )
    pdf.table_row(
        ["features/super-admin/...StaffRegisterPage.jsx", "Same if used"],
        widths=w2,
    )
    pdf.table_row(
        ["features/super-admin/...StaffDetailPage.jsx", "Same if used"],
        widths=w2,
    )

    # 5. Doctor UI details
    pdf.add_page()
    pdf.section_title("5. Doctor Module - Detailed UI Spec")
    pdf.sub_title("5.1 Suggested constants.js shape")
    pdf.code_block(
        """
export const LAB_DEPARTMENTS = [
  { code: 'LAB', label: 'Laboratory' },
  { code: 'RAD', label: 'Radiology' },
];

export const LAB_TESTS_BY_DEPARTMENT = {
  LAB: [
    'Blood Test', 'Urine Test', 'Stool Test',
    'Biochemistry', 'Hematology', 'Microbiology',
    'Histopathology', 'CBC', 'Lipid Profile',
    'Blood Sugar', 'Urine Routine',
  ],
  RAD: [
    'X-Ray', 'Ultrasound (USG)', 'CT Scan',
    'MRI', 'Mammography',
    'X-Ray Chest', 'MRI Brain', 'CT Scan Abdomen',
  ],
};

// Keep category as a soft label if needed (Blood/Urine/etc.),
// but department is the routing field.
"""
    )
    pdf.sub_title("5.2 Consultation / Labs UX rules")
    pdf.bullet("Show Lab Department dropdown FIRST (Laboratory | Radiology)")
    pdf.bullet("Load department options from /departments or /opd/departments filtered to LAB+RAD")
    pdf.bullet("OR hardcode labels and resolve id by matching department.code")
    pdf.bullet("Test dropdown options = LAB_TESTS_BY_DEPARTMENT[selectedCode]")
    pdf.bullet("If department changes, CLEAR selected test")
    pdf.bullet("Disable test dropdown until department is selected")
    pdf.bullet("On save, send department_id (numeric id from departments API)")
    pdf.bullet("Also send category for display (e.g. Blood / Radiology) if UI still uses it")

    pdf.sub_title("5.3 clinicalMapper.js - create payload")
    pdf.code_block(
        """
export function uiToApiLabTestCreate(ui) {
  return {
    appointment_id: ui.appointmentDbId,
    test_name: ui.testName ?? ui.test,
    category: ui.category,
    department_id: ui.departmentId ?? ui.department_id, // REQUIRED from new UI
    priority: ui.priority || 'Normal',
    clinical_notes: ui.clinicalNotes ?? ui.clinical_notes ?? '',
  };
}

// Also map department_id on update if doctor can change department/test.
"""
    )
    pdf.sub_title("5.4 Display department on doctor Labs list (optional but useful)")
    pdf.bullet("apiToUiLabTest: map department_id / departmentName if present")
    pdf.bullet("Show a badge: Laboratory or Radiology next to the order")

    # 6. Admin UI
    pdf.section_title("6. Admin / Super-Admin - Lab Tech Department")
    pdf.body(
        "Today department is required only for doctor. Extend the same pattern "
        "to lab_technician, but limit options to LAB and RAD."
    )
    pdf.bullet("needsDepartment / roleRequiresDepartment: doctor OR lab_technician")
    pdf.bullet(
        "Department options for lab_technician: filter departments where code is LAB or RAD"
    )
    pdf.bullet("For doctor: keep full clinical department list (exclude LAB from doctor list too)")
    pdf.bullet("Validation toast: 'Please select Laboratory or Radiology for lab technician'")
    pdf.bullet("Submit department_id in register and update payloads")
    pdf.code_block(
        """
const isLabTech = selectedRole?.name === 'lab_technician';
const needsDepartment =
  selectedRole?.name === 'doctor' || isLabTech;

const departmentOptions = departments
  .filter((d) => {
    const code = String(d.code || '').toUpperCase();
    if (isLabTech) return code === 'LAB' || code === 'RAD';
    // doctor clinical list - hide lab-only depts
    return code !== 'LAB';
  })
  .map((d) => ({ value: String(d.id), label: d.name }));
"""
    )

    # 7. Lab tech frontend
    pdf.section_title("7. Lab Technician Frontend")
    pdf.body(
        "Most lab tech pages need little change because backend already scopes data. "
        "Recommended UX polish:"
    )
    pdf.bullet("Show current department name in LabLayout / LabAppShell header")
    pdf.bullet("If API returns 403 (no department assigned), show clear message to contact admin")
    pdf.bullet("Do not rely on client-side category filter for security - backend already filters")
    pdf.bullet("Optional: map department_id in labMapper.js for display badges")

    files_lab = [pdf.epw * 0.62, pdf.epw * 0.38]
    pdf.table_row(["Optional polish files", "Action"], bold=True, widths=files_lab)
    pdf.table_row(
        ["features/lab/components/LabLayout.jsx", "Show LAB/RAD label"],
        widths=files_lab,
    )
    pdf.table_row(
        ["features/lab/components/LabAppShell.jsx", "Same"],
        widths=files_lab,
    )
    pdf.table_row(
        ["shared/api/mappers/labMapper.js", "Map department_id for UI"],
        widths=files_lab,
    )

    # 8. How to resolve department_id
    pdf.add_page()
    pdf.section_title("8. How Frontend Gets department_id")
    pdf.body(
        "Doctor UI needs numeric department_id for POST /lab-tests. Use existing departments API."
    )
    pdf.bullet("Fetch departments list (admin /departments or OPD /opd/departments)")
    pdf.bullet("Find row where code === 'LAB' or code === 'RAD'")
    pdf.bullet("Use that row's id as department_id")
    pdf.code_block(
        """
function resolveLabDepartmentId(departments, code) {
  const row = departments.find(
    (d) => String(d.code || '').toUpperCase() === code
  );
  return row ? Number(row.id) : null;
}

// On save:
department_id: resolveLabDepartmentId(allDepartments, selectedCode) // 'LAB' | 'RAD'
"""
    )
    pdf.callout(
        "SEED REQUIREMENT",
        "Database must have departments Laboratory (LAB) and Radiology (RAD). "
        "Backend seed.py already includes both. Run seed if LAB is missing.",
    )

    # 9. Acceptance criteria
    pdf.section_title("9. Acceptance Criteria (QA Checklist)")
    pdf.sub_title("OPD Billing")
    pdf.bullet("Register Patient department dropdown does NOT show Laboratory")
    pdf.bullet("Doctor clinical departments still appear (Cardiology, Pediatrics, ...)")
    pdf.sub_title("Doctor module")
    pdf.bullet("Lab order form shows Laboratory / Radiology department selector")
    pdf.bullet("Selecting Laboratory shows only laboratory tests")
    pdf.bullet("Selecting Radiology shows only radiology/imaging tests")
    pdf.bullet("Changing department clears previously selected test")
    pdf.bullet("Created order includes department_id in network payload")
    pdf.sub_title("Admin")
    pdf.bullet("Creating lab_technician requires selecting Laboratory or Radiology")
    pdf.bullet("Cannot assign Cardiology etc. to lab technician")
    pdf.sub_title("Lab technician")
    pdf.bullet("Laboratory tech sees only Laboratory orders")
    pdf.bullet("Radiology tech sees only Radiology orders")
    pdf.bullet("Cannot open other department order by URL/id (404/403 from API)")
    pdf.bullet("Notifications only for own department orders")

    # 10. Out of scope
    pdf.section_title("10. Out of Scope")
    pdf.bullet("No new lab_test_catalog table / model")
    pdf.bullet("No new role names (keep single role: lab_technician)")
    pdf.bullet("No new /lab routes - same portal, filtered data")
    pdf.bullet("No backend file changes for this frontend task")

    # 11. Implementation order
    pdf.section_title("11. Suggested Frontend Implementation Order")
    pdf.bullet("1) opdReference.js - hide LAB from OPD clinical dropdowns (quick win)")
    pdf.bullet("2) Admin staff register/detail - assign LAB/RAD to lab techs")
    pdf.bullet("3) doctor/constants.js - department + test maps")
    pdf.bullet("4) clinicalMapper.js - add department_id to create/update")
    pdf.bullet("5) ConsultationModal.jsx + LabsSection.jsx - UI wiring")
    pdf.bullet("6) Optional lab shell badge + 403 empty state")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(20, 60, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 7, "Document end - Frontend Lab Department Guide")

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
