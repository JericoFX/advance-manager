const isFiveMEnvironment = typeof GetParentResourceName !== 'undefined';

const defaultMockBusiness = {
    id: 1,
    name: 'Los Santos Police Department',
    jobName: 'police',
    jobLabel: 'Police Department',
    funds: 45230,
    owner: 'ABC12345',
    user: {
        name: 'John Doe',
        role: 'boss'
    },
    employees: [
        { id: 1, name: 'Jane Smith', citizenid: 'DEF67890', grade: 2, wage: 45 },
        { id: 2, name: 'Bob Johnson', citizenid: 'GHI01234', grade: 1, wage: 35 },
        { id: 3, name: 'Alice Brown', citizenid: 'JKL56789', grade: 3, wage: 55 }
    ],
    gradeMetadata: [
        { value: 0, label: 'Cadet', wage: 25, isboss: false },
        { value: 1, label: 'Officer', wage: 35, isboss: false },
        { value: 2, label: 'Sergeant', wage: 45, isboss: false },
        { value: 3, label: 'Lieutenant', wage: 55, isboss: false },
        { value: 4, label: 'Captain', wage: 75, isboss: true }
    ],
    wageLimits: { min: 0, max: 1000 },
    jobInfo: {
        grades: {
            '0': { label: 'Cadet', payment: 25, isboss: false },
            '1': { label: 'Officer', payment: 35, isboss: false },
            '2': { label: 'Sergeant', payment: 45, isboss: false },
            '3': { label: 'Lieutenant', payment: 55, isboss: false },
            '4': { label: 'Captain', payment: 75, isboss: true }
        }
    }
};

// Funciones específicas para el manejo de negocios
const BusinessAPI = {
    gradeDefinitions: [],
    wagesByGrade: {},
    wageLimits: { min: 0, max: 10000 },

    // Simular datos del negocio
    currentBusiness: isFiveMEnvironment ? {} : { ...defaultMockBusiness },

    updateFromServer(payload = {}) {
        if (!payload || typeof payload !== 'object') {
            return;
        }

        const wageLimits = payload.wageLimits || payload.wage_limits;
        if (wageLimits && typeof wageLimits === 'object') {
            const min = Number(wageLimits.min);
            const max = Number(wageLimits.max);
            if (Number.isFinite(min)) {
                this.wageLimits.min = min;
            }
            if (Number.isFinite(max)) {
                this.wageLimits.max = max;
            }
        }

        const gradeDefinitions = this.extractGradeDefinitions(payload);
        if (gradeDefinitions.length > 0) {
            this.gradeDefinitions = gradeDefinitions;
            this.wagesByGrade = {};

            gradeDefinitions.forEach((definition) => {
                if (Number.isFinite(definition.wage)) {
                    this.wagesByGrade[definition.value] = definition.wage;
                }
            });
        }
    },

    extractGradeDefinitions(payload = {}) {
        const definitions = [];
        const gradeMetadata = payload.gradeMetadata || payload.grade_metadata;
        const jobInfo = payload.jobInfo || payload.job_info;

        if (Array.isArray(gradeMetadata) && gradeMetadata.length > 0) {
            gradeMetadata.forEach((entry) => {
                const value = Number(entry.value ?? entry.grade);
                if (!Number.isFinite(value)) {
                    return;
                }

                const label = entry.label || entry.name || `Grade ${value}`;
                const wage = Number(entry.wage ?? entry.payment);
                definitions.push({ value, label, wage: Number.isFinite(wage) ? wage : null, isboss: Boolean(entry.isboss) });
            });
        } else if (jobInfo && jobInfo.grades && typeof jobInfo.grades === 'object') {
            Object.entries(jobInfo.grades).forEach(([gradeKey, gradeData]) => {
                const value = Number(gradeKey);
                if (!Number.isFinite(value)) {
                    return;
                }

                const label = gradeData.label || gradeData.name || `Grade ${value}`;
                const wage = Number(gradeData.payment);
                definitions.push({ value, label, wage: Number.isFinite(wage) ? wage : null, isboss: Boolean(gradeData.isboss) });
            });
        }

        if (definitions.length === 0 && Array.isArray(defaultMockBusiness.gradeMetadata)) {
            defaultMockBusiness.gradeMetadata.forEach((entry) => {
                const value = Number(entry.value);
                if (!Number.isFinite(value)) {
                    return;
                }

                const label = entry.label || `Grade ${value}`;
                const wage = Number(entry.wage);
                definitions.push({ value, label, wage: Number.isFinite(wage) ? wage : null, isboss: Boolean(entry.isboss) });
            });
        }

        definitions.sort((a, b) => a.value - b.value);

        return definitions;
    },

    // Obtener información del negocio
    getBusinessInfo() {
        return new Promise((resolve) => {
            // Simular delay de API
            setTimeout(() => {
                const business = { ...this.currentBusiness };

                this.updateFromServer(business);

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                    BusinessManager.setSyncedEmployees(business.employees || []);
                }

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.updateEmployeeCount === 'function') {
                    BusinessManager.updateEmployeeCount(business.employees?.length);
                }

                resolve(business);
            }, 500);
        });
    },
    
    // Depositar fondos
    depositFunds(amount) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                if (amount <= 0) {
                    reject({ error: 'Invalid amount' });
                    return;
                }
                
                // Simular verificación de dinero del jugador
                const playerCash = 10000; // Simular dinero del jugador
                
                if (amount > playerCash) {
                    reject({ error: 'Insufficient funds' });
                    return;
                }
                
                this.currentBusiness.funds += amount;
                resolve({ 
                    success: true, 
                    message: `Successfully deposited $${amount.toLocaleString()}`,
                    newBalance: this.currentBusiness.funds
                });
            }, 1000);
        });
    },
    
    // Retirar fondos
    withdrawFunds(amount) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                if (amount <= 0) {
                    reject({ error: 'Invalid amount' });
                    return;
                }
                
                if (amount > this.currentBusiness.funds) {
                    reject({ error: 'Insufficient business funds' });
                    return;
                }
                
                this.currentBusiness.funds -= amount;
                resolve({ 
                    success: true, 
                    message: `Successfully withdrew $${amount.toLocaleString()}`,
                    newBalance: this.currentBusiness.funds
                });
            }, 1000);
        });
    },
    
    // Contratar empleado
    hireEmployee(playerId, grade, wage) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                // Simular verificación de jugador
                const playerNames = ['Mike Wilson', 'Sarah Connor', 'Tom Hardy', 'Emma Stone'];
                const randomName = playerNames[Math.floor(Math.random() * playerNames.length)];

                if (!playerId || playerId <= 0) {
                    reject({ error: 'Invalid player ID' });
                    return;
                }

                const grades = this.getGrades();
                const gradeValues = Array.isArray(grades) ? grades.map((g) => g.value) : [];
                const minGrade = gradeValues.length > 0 ? Math.min(...gradeValues) : 0;
                const maxGrade = gradeValues.length > 0 ? Math.max(...gradeValues) : 0;

                if (!Number.isInteger(grade) || grade < minGrade || grade > maxGrade || (gradeValues.length > 0 && !gradeValues.includes(grade))) {
                    reject({ error: `Invalid grade level (${minGrade}-${maxGrade})` });
                    return;
                }

                const assignedWage = Number.isFinite(wage) ? wage : this.getWageForGrade(grade);
                const minWage = Number.isFinite(this.wageLimits.min) ? this.wageLimits.min : 0;
                const maxWage = Number.isFinite(this.wageLimits.max) ? this.wageLimits.max : 10000;

                if (!Number.isFinite(assignedWage) || assignedWage < minWage || assignedWage > maxWage) {
                    reject({ error: `Invalid wage amount (${minWage}-${maxWage})` });
                    return;
                }

                const newEmployee = {
                    id: this.currentBusiness.employees.length + 1,
                    name: randomName,
                    citizenid: `CID${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
                    grade: grade,
                    wage: assignedWage
                };

                this.currentBusiness.employees.push(newEmployee);

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                    BusinessManager.setSyncedEmployees(this.currentBusiness.employees);
                }

                resolve({
                    success: true,
                    message: `Successfully hired ${randomName} at grade ${grade}`,
                    employee: newEmployee
                });
            }, 1500);
        });
    },
    
    // Despedir empleado
    fireEmployee(citizenId) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                const employeeIndex = this.currentBusiness.employees.findIndex(emp => emp.citizenid === citizenId);

                if (employeeIndex === -1) {
                    reject({ error: 'Employee not found' });
                    return;
                }
                
                const employee = this.currentBusiness.employees[employeeIndex];
                this.currentBusiness.employees.splice(employeeIndex, 1);

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                    BusinessManager.setSyncedEmployees(this.currentBusiness.employees);
                }

                resolve({
                    success: true,
                    message: `${employee.name} has been fired`,
                    employee: employee
                });
            }, 1000);
        });
    },
    
    // Actualizar salario de empleado
    updateEmployeeWage(citizenId, newWage) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                const employee = this.currentBusiness.employees.find(emp => emp.citizenid === citizenId);

                if (!employee) {
                    reject({ error: 'Employee not found' });
                    return;
                }

                const minWage = Number.isFinite(this.wageLimits.min) ? this.wageLimits.min : 0;
                const maxWage = Number.isFinite(this.wageLimits.max) ? this.wageLimits.max : 10000;

                if (!Number.isFinite(newWage) || newWage < minWage || newWage > maxWage) {
                    reject({ error: `Invalid wage amount (${minWage}-${maxWage})` });
                    return;
                }

                employee.wage = newWage;

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                    BusinessManager.setSyncedEmployees(this.currentBusiness.employees);
                }

                resolve({
                    success: true,
                    message: `Updated ${employee.name}'s wage to $${newWage}/hour`,
                    employee: employee
                });
            }, 1000);
        });
    },
    
    // Actualizar grado de empleado
    updateEmployeeGrade(citizenId, newGrade, wage) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                const employee = this.currentBusiness.employees.find(emp => emp.citizenid === citizenId);

                if (!employee) {
                    reject({ error: 'Employee not found' });
                    return;
                }

                const grades = this.getGrades();
                const gradeValues = Array.isArray(grades) ? grades.map((g) => g.value) : [];
                const minGrade = gradeValues.length > 0 ? Math.min(...gradeValues) : 0;
                const maxGrade = gradeValues.length > 0 ? Math.max(...gradeValues) : 0;

                if (!Number.isInteger(newGrade) || newGrade < minGrade || newGrade > maxGrade || (gradeValues.length > 0 && !gradeValues.includes(newGrade))) {
                    reject({ error: `Invalid grade level (${minGrade}-${maxGrade})` });
                    return;
                }

                employee.grade = newGrade;

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                    BusinessManager.setSyncedEmployees(this.currentBusiness.employees);
                }

                resolve({
                    success: true,
                    message: `Updated ${employee.name}'s grade to ${newGrade}`,
                    employee: employee
                });
            }, 1000);
        });
    },
    
    // Obtener empleados
    getEmployees() {
        return new Promise((resolve) => {
            setTimeout(() => {
                const employees = this.currentBusiness.employees;

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                    BusinessManager.setSyncedEmployees(employees);
                }

                if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.updateEmployeeCount === 'function') {
                    BusinessManager.updateEmployeeCount(employees?.length);
                }

                resolve(employees);
            }, 500);
        });
    },
    
    // Obtener grados disponibles
    getGrades() {
        if (Array.isArray(this.gradeDefinitions) && this.gradeDefinitions.length > 0) {
            return this.gradeDefinitions.map((definition) => ({
                value: definition.value,
                label: `Grade ${definition.value} - ${definition.label}`,
                wage: definition.wage
            }));
        }

        return [
            { value: 0, label: 'Grade 0 - Cadet', wage: 25 },
            { value: 1, label: 'Grade 1 - Officer', wage: 35 },
            { value: 2, label: 'Grade 2 - Sergeant', wage: 45 },
            { value: 3, label: 'Grade 3 - Lieutenant', wage: 55 },
            { value: 4, label: 'Grade 4 - Captain', wage: 75 }
        ];
    },

    // Obtener sueldo por grado
    getWageForGrade(grade) {
        const wage = this.wagesByGrade[grade];
        return Number.isFinite(wage) ? wage : null;
    },
    
    // Formatear dinero
    formatMoney(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    },
    
    // Obtener nombre del grado
    getGradeName(grade) {
        const grades = this.getGrades();
        const gradeInfo = grades.find(g => g.value === grade);
        return gradeInfo ? gradeInfo.label : `Grade ${grade}`;
    }
};

BusinessAPI.updateFromServer(BusinessAPI.currentBusiness);

// Extender BusinessManager con funciones API
if (typeof BusinessManager !== 'undefined') {
    Object.assign(BusinessManager, {
        syncedEmployees: isFiveMEnvironment
            ? []
            : (Array.isArray(BusinessAPI.currentBusiness?.employees)
                ? [...BusinessAPI.currentBusiness.employees]
                : []),

        setSyncedEmployees(employees = []) {
            const normalized = Array.isArray(employees) ? [...employees] : [];
            this.syncedEmployees = normalized;

            if (BusinessAPI.currentBusiness) {
                BusinessAPI.currentBusiness.employees = [...normalized];
            }
        },

        getSyncedEmployees() {
            return Array.isArray(this.syncedEmployees) ? this.syncedEmployees : [];
        },

        async syncEmployeesFromServer() {
            try {
                const employees = await BusinessAPI.getEmployees();
                return employees;
            } catch (error) {
                console.error('Failed to sync employees from server', error);
                return this.getSyncedEmployees();
            }
        },

        // Sobrescribir funciones para usar API simulada
        async handleDeposit() {
            const amount = parseInt($('#depositAmount').val());
            if (!amount || amount <= 0) {
                this.showToast('Please enter a valid amount', 'error');
                return;
            }
            
            try {
                this.showLoading('Processing deposit...');
                const result = await BusinessAPI.depositFunds(amount);
                this.hideLoading();
                
                this.showToast(result.message, 'success');
                this.updateFunds(result.newBalance);
                this.hideModal();
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to deposit funds', 'error');
            }
        },
        
        async handleWithdraw() {
            const amount = parseInt($('#withdrawAmount').val());
            if (!amount || amount <= 0) {
                this.showToast('Please enter a valid amount', 'error');
                return;
            }
            
            try {
                this.showLoading('Processing withdrawal...');
                const result = await BusinessAPI.withdrawFunds(amount);
                this.hideLoading();
                
                this.showToast(result.message, 'success');
                this.updateFunds(result.newBalance);
                this.hideModal();
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to withdraw funds', 'error');
            }
        },
        
        async handleHire() {
            const playerId = parseInt($('#playerId').val());
            const grade = parseInt($('#gradeLevel').val());
            const confirmButton = $('#modalConfirm');
            let wage = Number(confirmButton.data('wage'));

            if (!Number.isFinite(wage)) {
                wage = this.getWageForGrade(grade);
                confirmButton.data('wage', wage);
            }

            if (!playerId) {
                this.showToast('Please enter a player ID', 'error');
                return;
            }

            if (!Number.isInteger(wage) || wage <= 0) {
                this.showToast('Invalid wage amount', 'error');
                return;
            }

            try {
                this.showLoading('Hiring employee...');
                const result = await BusinessAPI.hireEmployee(playerId, grade, wage);
                this.hideLoading();

                this.showToast(result.message, 'success');

                let employees;
                if (typeof this.syncEmployeesFromServer === 'function') {
                    employees = await this.syncEmployeesFromServer();
                }

                this.updateEmployeeCount(employees?.length);
                this.hideModal();
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to hire employee', 'error');
            }
        },

        async fireEmployee(id) {
            try {
                this.showLoading('Firing employee...');
                const result = await BusinessAPI.fireEmployee(citizenId);
                this.hideLoading();

                this.showToast(result.message, 'success');

                let employees;
                if (typeof this.syncEmployeesFromServer === 'function') {
                    employees = await this.syncEmployeesFromServer();
                }

                this.updateEmployeeCount(employees?.length);

                // Actualizar lista si está abierta
                if (this.currentAction === 'manage') {
                    this.showEmployeesList();
                }
            } catch (error) {
                this.hideLoading();
                this.showToast(error.error || 'Failed to fire employee', 'error');
            }
        },

        updateEmployeeCount(count) {
            if (typeof count === 'number') {
                $('#totalEmployees').text(count);
                return;
            }

            const employees = this.getSyncedEmployees();
            $('#totalEmployees').text(employees.length);
        },

        showLoading(message) {
            // Crear overlay de carga
            const loader = $(`
                <div class="loading-overlay" style="
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 9999;
                ">
                    <div style="
                        background: var(--bg-secondary);
                        border: 1px solid var(--border-color);
                        border-radius: 12px;
                        padding: 2rem;
                        display: flex;
                        align-items: center;
                        gap: 1rem;
                        color: var(--text-primary);
                    ">
                        <i class="fas fa-spinner fa-spin" style="font-size: 1.5rem; color: var(--primary-color);"></i>
                        <span>${message}</span>
                    </div>
                </div>
            `);
            
            $('body').append(loader);
        },
        
        hideLoading() {
            $('.loading-overlay').remove();
        }
    });
}
