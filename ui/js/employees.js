// Funciones específicas para el manejo de empleados
const EmployeeManager = {
    // Implements: IDEA-05 – align UI payload contracts with shared job data
    // Mostrar lista actualizada de empleados
    async showEmployeesList() {
        try {
            const employees = await BusinessAPI.getEmployees();

            if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                BusinessManager.setSyncedEmployees(employees);
            }

            let body = '<div class="employees-list">';

            if (employees.length === 0) {
                body += `
                    <div style="
                        text-align: center;
                        padding: 2rem;
                        color: var(--text-muted);
                    ">
                        <i class="fas fa-user-slash" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                        <p>No employees found</p>
                    </div>
                `;
            } else {
                employees.forEach(emp => {
                    body += this.createEmployeeCard(emp);
                });
            }
            
            body += '</div>';
            
            BusinessManager.showModal('Manage Employees', body, 'Close');
            BusinessManager.currentAction = 'manage';
        } catch (error) {
            BusinessManager.showToast('Failed to load employees', 'error');
        }
    },
    
    // Crear tarjeta de empleado
    createEmployeeCard(employee) {
        const gradeName = BusinessAPI.getGradeName(employee.grade);
        
        const encodedCitizenId = encodeURIComponent(employee.citizenid);
        const encodedName = encodeURIComponent(employee.name);

        return `
            <div class="employee-card" style="
                background: rgba(51, 65, 85, 0.3);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 1.25rem;
                margin-bottom: 1rem;
                transition: var(--transition);
            " onmouseover="this.style.borderColor='var(--primary-color)'" 
               onmouseout="this.style.borderColor='var(--border-color)'">
                <div class="employee-header" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 0.75rem;
                ">
                    <div>
                        <h4 style="
                            font-weight: 600;
                            color: var(--text-primary);
                            margin-bottom: 0.25rem;
                            font-size: 1rem;
                        ">${employee.name}</h4>
                        <p style="
                            color: var(--text-secondary);
                            font-size: 0.875rem;
                            margin-bottom: 0.5rem;
                        ">${gradeName}</p>
                    </div>
                    <div class="employee-actions" style="
                        display: flex;
                        gap: 0.5rem;
                        flex-shrink: 0;
                    ">
                        <button class="btn btn-info"
                                style="padding: 0.5rem; font-size: 0.75rem; min-width: auto;"
                                data-employee-id="${employee.id}"
                                data-citizenid="${encodedCitizenId}"
                                data-grade="${employee.grade}"
                                data-wage="${employee.wage}"
                                data-name="${encodedName}"
                                onclick="EmployeeManager.showEditModal(this)"
                                title="Edit Employee">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-danger"
                                style="padding: 0.5rem; font-size: 0.75rem; min-width: auto;"
                                data-employee-id="${employee.id}"
                                data-citizenid="${encodedCitizenId}"
                                data-wage="${employee.wage}"
                                data-name="${encodedName}"
                                onclick="EmployeeManager.confirmFire(this)"
                                title="Fire Employee">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                
                <div class="employee-details" style="
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 1rem;
                    padding-top: 0.75rem;
                    border-top: 1px solid rgba(51, 65, 85, 0.5);
                ">
                    <div>
                        <span style="
                            color: var(--text-muted);
                            font-size: 0.75rem;
                            text-transform: uppercase;
                            letter-spacing: 0.5px;
                        ">Grade Level</span>
                        <p style="
                            color: var(--text-primary);
                            font-weight: 600;
                            margin-top: 0.25rem;
                        ">${employee.grade}</p>
                    </div>
                    <div>
                        <span style="
                            color: var(--text-muted);
                            font-size: 0.75rem;
                            text-transform: uppercase;
                            letter-spacing: 0.5px;
                        ">Hourly Wage</span>
                        <p style="
                            color: var(--success-color);
                            font-weight: 600;
                            margin-top: 0.25rem;
                            font-family: 'Courier New', monospace;
                        ">$${employee.wage}</p>
                    </div>
                </div>
            </div>
        `;
    },
    
    // Mostrar modal de edición
    async showEditModal(triggerElement) {
        const element = triggerElement instanceof HTMLElement ? triggerElement : null;
        const dataset = element ? element.dataset : {};
        const citizenId = dataset.citizenid ? decodeURIComponent(dataset.citizenid) : null;
        const employeeId = dataset.employeeId ? parseInt(dataset.employeeId, 10) : null;

        let employeesList;

        try {
            employeesList = await BusinessAPI.getEmployees();
        } catch (error) {
            BusinessManager.showToast('Failed to load employees', 'error');
            return;
        }

        if (!Array.isArray(employeesList)) {
            BusinessManager.showToast('Invalid employees data', 'error');
            return;
        }

        let employee = null;

        if (citizenId) {
            employee = employeesList.find(emp => emp.citizenid === citizenId);
        }

        if (!employee && employeeId) {
            employee = employeesList.find(emp => emp.id === employeeId);
        }

        if (!employee) {
            BusinessManager.showToast('Employee not found', 'error');
            return;
        }

        const gradeFromDataset = dataset.grade ? parseInt(dataset.grade, 10) : employee.grade;
        const wageFromDataset = dataset.wage ? parseInt(dataset.wage, 10) : employee.wage;
        
        const grades = BusinessAPI.getGrades();
        const gradeWage = BusinessAPI.getWageForGrade(employee.grade);
        const initialWage = Number.isInteger(gradeWage) ? gradeWage : employee.wage;
        let gradeOptions = '';
        
        grades.forEach(grade => {
            gradeOptions += `<option value="${grade.value}" data-wage="${grade.wage ?? ''}" ${grade.value === gradeFromDataset ? 'selected' : ''}>${grade.label}</option>`;
        });

        const body = `
            <div class="employee-edit-form">
                <div class="input-group">
                    <label class="input-label">Employee Name</label>
                    <input type="text" class="input-field" value="${employee.name}" disabled
                           style="opacity: 0.6; cursor: not-allowed;">
                </div>

                <div class="input-group">
                    <label class="input-label">Grade Level</label>
                    <select class="input-field" id="editGrade">
                        ${gradeOptions}
                    </select>
                </div>

                <div class="input-group">
                    <label class="input-label">Hourly Wage</label>
                    <input type="number" class="input-field" id="editWage"
                           value="${wageFromDataset}"
                           readonly data-wage="${wageFromDataset}"
                           style="opacity: 0.6; cursor: not-allowed;">
                    <p id="editWageFeedback" style="color: var(--text-muted); font-size: 0.75rem; margin-top: 0.25rem;">Wage is automatically set based on grade from QBCore shared</p>
                </div>

                <div style="
                    background: rgba(37, 99, 235, 0.1);
                    border: 1px solid rgba(37, 99, 235, 0.3);
                    border-radius: 8px;
                    padding: 1rem;
                    margin-top: 1rem;
                ">
                    <h4 style="
                        color: var(--primary-color);
                        margin-bottom: 0.5rem;
                        font-size: 0.875rem;
                    ">Employee Information</h4>
                    <p style="
                        color: var(--text-secondary);
                        font-size: 0.875rem;
                        margin-bottom: 0.25rem;
                    ">Citizen ID: ${employee.citizenid}</p>
                    <p style="
                        color: var(--text-secondary);
                        font-size: 0.875rem;
                    ">Current Grade: ${BusinessAPI.getGradeName(employee.grade)}</p>
                </div>
            </div>
        `;

        BusinessManager.showModal('Edit Employee', body, 'Save Changes');
        BusinessManager.currentAction = 'editEmployee';
        BusinessManager.editingEmployeeId = citizenId || employeeId;

        const confirmButton = $('#modalConfirm');
        confirmButton.data('citizenid', employee.citizenid);
        confirmButton.data('wage', wageFromDataset);

        setTimeout(() => {
            $('#editGrade').on('change', function() {
                const selectedGrade = parseInt($(this).val(), 10);
                const newWage = BusinessManager.getWageForGrade(selectedGrade);
                if (Number.isFinite(newWage)) {
                    $('#editWage').val(newWage).data('wage', newWage);
                    confirmButton.data('wage', newWage);
                }
            });
        }, 0);
    },

    // Confirmar despido
    confirmFire(triggerElement) {
        const element = triggerElement instanceof HTMLElement ? triggerElement : null;
        const dataset = element ? element.dataset : {};
        const citizenId = dataset.citizenid ? decodeURIComponent(dataset.citizenid) : null;
        const employeeName = dataset.name ? decodeURIComponent(dataset.name) : 'this employee';

        const body = `
            <div style="text-align: center; padding: 1rem;">
                <i class="fas fa-exclamation-triangle" style="
                    font-size: 3rem;
                    color: var(--warning-color);
                    margin-bottom: 1rem;
                "></i>
                <h3 style="
                    color: var(--text-primary);
                    margin-bottom: 1rem;
                ">Confirm Employee Termination</h3>
                <p style="
                    color: var(--text-secondary);
                    margin-bottom: 1.5rem;
                ">Are you sure you want to fire <strong>${employeeName}</strong>?</p>
                <p style="
                    color: var(--text-muted);
                    font-size: 0.875rem;
                ">This action cannot be undone.</p>
            </div>
        `;

        BusinessManager.showModal('Confirm Action', body, 'Fire Employee');
        BusinessManager.currentAction = 'confirmFire';
        BusinessManager.firingEmployeeId = citizenId;

        // Cambiar color del botón de confirmación
        $('#modalConfirm').removeClass('btn-primary').addClass('btn-danger');
        $('#modalConfirm').data('citizenid', citizenId);
        $('#modalConfirm').data('wage', dataset.wage ? parseInt(dataset.wage, 10) : null);
    },

    // Manejar edición de empleado
    async handleEditEmployee() {
        const confirmButton = $('#modalConfirm');
        const citizenId = confirmButton.data('citizenid');
        const newGrade = parseInt($('#editGrade').val());
        const newWage = parseInt($('#editWage').val());
        const wageLimits = BusinessAPI?.wageLimits || { min: 0, max: 10000 };
        const minWage = Number.isFinite(Number(wageLimits.min)) ? Number(wageLimits.min) : 0;
        const maxWage = Number.isFinite(Number(wageLimits.max)) ? Number(wageLimits.max) : 10000;

        if (!Number.isFinite(newWage) || newWage < minWage || newWage > maxWage) {
            BusinessManager.showToast(`Invalid wage amount (${minWage}-${maxWage})`, 'error');
            return;
        }

        if (!citizenId) {
            BusinessManager.showToast('Missing employee data', 'error');
            return;
        }

        try {
            BusinessManager.showLoading('Updating employee...');

            // Actualizar grado si cambió
            const employees = await BusinessAPI.getEmployees();
            const employee = employees.find(emp => emp.citizenid === citizenId);

            if (!employee) {
                throw { error: 'Employee not found' };
            }

            if (employee.grade !== newGrade) {
                await BusinessAPI.updateEmployeeGrade(citizenId, newGrade, newWage);
            }

            // Actualizar salario si cambió
            if (employee.wage !== newWage) {
                await BusinessAPI.updateEmployeeWage(citizenId, newWage);
            }

            BusinessManager.hideLoading();
            BusinessManager.showToast('Employee updated successfully', 'success');
            BusinessManager.hideModal();

            // Refrescar lista y sincronizar empleados
            if (typeof BusinessManager.syncEmployeesFromServer === 'function') {
                const refreshedEmployees = await BusinessManager.syncEmployeesFromServer();
                BusinessManager.updateEmployeeCount(refreshedEmployees?.length);
            }

            this.showEmployeesList();
        } catch (error) {
            BusinessManager.hideLoading();
            BusinessManager.showToast(error.error || 'Failed to update employee', 'error');
        }
    },

    // Manejar confirmación de despido
    async handleConfirmFire() {
        const confirmButton = $('#modalConfirm');
        const citizenId = confirmButton.data('citizenid') || BusinessManager.firingEmployeeId;

        if (!citizenId) {
            BusinessManager.showToast('Missing employee data', 'error');
            return;
        }

        try {
            BusinessManager.showLoading('Firing employee...');
            const result = await BusinessAPI.fireEmployee(citizenId);
            BusinessManager.hideLoading();

            BusinessManager.showToast(result.message, 'success');
            BusinessManager.hideModal();

            let syncedEmployees = [];

            if (typeof BusinessManager.syncEmployeesFromServer === 'function') {
                syncedEmployees = await BusinessManager.syncEmployeesFromServer();
            }

            BusinessManager.updateEmployeeCount(syncedEmployees?.length);

            // Refrescar lista
            this.showEmployeesList();
        } catch (error) {
            BusinessManager.hideLoading();
            BusinessManager.showToast(error.error || 'Failed to fire employee', 'error');
        }
    }
};

// Extender BusinessManager con funciones de empleados
if (typeof BusinessManager !== 'undefined') {
    Object.assign(BusinessManager, {
        // Sobrescribir showEmployeesList
        showEmployeesList() {
            EmployeeManager.showEmployeesList();
        },
        
        // Añadir nuevos handlers
        async handleModalConfirm() {
            switch(this.currentAction) {
                case 'deposit':
                    await this.handleDeposit();
                    break;
                case 'withdraw':
                    await this.handleWithdraw();
                    break;
                case 'hire':
                    await this.handleHire();
                    break;
                case 'editEmployee':
                    await EmployeeManager.handleEditEmployee();
                    break;
                case 'confirmFire':
                    await EmployeeManager.handleConfirmFire();
                    break;
                case 'manage':
                    this.hideModal();
                    break;
            }
        },
        
        // Limpiar al cerrar modal
        hideModal() {
            $('#modal').removeClass('active');
            this.currentAction = null;
            this.editingEmployeeId = null;
            this.firingEmployeeId = null;

            // Restaurar botón de confirmación
            $('#modalConfirm').removeClass('btn-danger').addClass('btn-primary');
            $('#modalConfirm').removeData('citizenid').removeData('wage');
        }
    });
}
