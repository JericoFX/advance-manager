// Funciones específicas para el manejo de empleados
const EmployeeManager = {
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
                                onclick="EmployeeManager.showEditModal(${employee.id})"
                                title="Edit Employee">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-danger" 
                                style="padding: 0.5rem; font-size: 0.75rem; min-width: auto;"
                                onclick="EmployeeManager.confirmFire(${employee.id}, '${employee.name}')"
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
    async showEditModal(employeeId) {
        let employees = [];

        if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.getSyncedEmployees === 'function') {
            employees = BusinessManager.getSyncedEmployees();

            if (!employees.length && typeof BusinessManager.syncEmployeesFromServer === 'function') {
                employees = await BusinessManager.syncEmployeesFromServer();
            }
        } else if (BusinessAPI.currentBusiness?.employees) {
            employees = BusinessAPI.currentBusiness.employees;
        } else {
            employees = await BusinessAPI.getEmployees();
        }

        const employee = employees.find(emp => emp.id === employeeId);

        if (!employee) {
            BusinessManager.showToast('Employee not found', 'error');
            return;
        }
        
        const grades = BusinessAPI.getGrades();
        let gradeOptions = '';
        
        grades.forEach(grade => {
            gradeOptions += `<option value="${grade.value}" ${grade.value === employee.grade ? 'selected' : ''}>${grade.label}</option>`;
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
                    <input type="text" class="input-field" id="editWage" 
                           value="$${employee.wage}/hour" readonly 
                           style="opacity: 0.6; cursor: not-allowed;">
                    <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 0.25rem;">Wage is automatically set based on grade from QBCore shared</p>
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
        BusinessManager.editingEmployeeId = employeeId;
    },
    
    // Confirmar despido
    confirmFire(employeeId, employeeName) {
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
        BusinessManager.firingEmployeeId = employeeId;
        
        // Cambiar color del botón de confirmación
        $('#modalConfirm').removeClass('btn-primary').addClass('btn-danger');
    },
    
    // Manejar edición de empleado
    async handleEditEmployee() {
        const employeeId = BusinessManager.editingEmployeeId;
        const newGrade = parseInt($('#editGrade').val());
        const newWage = parseInt($('#editWage').val());

        if (!newWage || newWage < 10 || newWage > 100) {
            BusinessManager.showToast('Invalid wage amount (10-100)', 'error');
            return;
        }

        try {
            BusinessManager.showLoading('Updating employee...');

            // Actualizar grado si cambió
            let employeeList = [];

            if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.getSyncedEmployees === 'function') {
                employeeList = BusinessManager.getSyncedEmployees();
            }

            if ((!employeeList || employeeList.length === 0) && typeof BusinessManager.syncEmployeesFromServer === 'function') {
                employeeList = await BusinessManager.syncEmployeesFromServer();
            }

            if (!employeeList || employeeList.length === 0) {
                employeeList = BusinessAPI.currentBusiness?.employees || [];
            }

            const employee = employeeList.find(emp => emp.id === employeeId);

            if (!employee) {
                BusinessManager.hideLoading();
                BusinessManager.showToast('Employee not found', 'error');
                return;
            }
            if (employee.grade !== newGrade) {
                await BusinessAPI.updateEmployeeGrade(employeeId, newGrade);
            }

            // Actualizar salario si cambió
            if (employee.wage !== newWage) {
                await BusinessAPI.updateEmployeeWage(employeeId, newWage);
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
        const employeeId = BusinessManager.firingEmployeeId;

        try {
            BusinessManager.showLoading('Firing employee...');
            const result = await BusinessAPI.fireEmployee(employeeId);
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
        }
    });
}
