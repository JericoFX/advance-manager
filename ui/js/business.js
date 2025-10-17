// Funciones específicas para el manejo de negocios
const BusinessAPI = {
    // Tabla de salarios por grado (simulado desde el servidor)
    wagesByGrade: [25, 35, 45, 55, 75],

    // Simular datos del negocio
    currentBusiness: {
        id: 1,
        name: 'Los Santos Police Department',
        jobName: 'police',
        funds: 45230,
        owner: 'ABC12345',
        employees: [
            { id: 1, name: 'Jane Smith', citizenid: 'DEF67890', grade: 2, wage: 45 },
            { id: 2, name: 'Bob Johnson', citizenid: 'GHI01234', grade: 1, wage: 35 },
            { id: 3, name: 'Alice Brown', citizenid: 'JKL56789', grade: 3, wage: 55 }
        ]
    },
    
    // Obtener información del negocio
    getBusinessInfo() {
        return new Promise((resolve) => {
            // Simular delay de API
            setTimeout(() => {
                const business = { ...this.currentBusiness };

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

                if (grade < 0 || grade > 4) {
                    reject({ error: 'Invalid grade level' });
                    return;
                }

                // Simular wage según el grade (esto vendría del servidor)
                const wagesByGrade = [25, 35, 45, 55, 75]; // Ejemplo de wages por grade
                const assignedWage = Number.isFinite(wage) ? wage : wagesByGrade[grade];

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
                
                if (newWage < 10 || newWage > 100) {
                    reject({ error: 'Invalid wage amount' });
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
                
                if (newGrade < 0 || newGrade > 4) {
                    reject({ error: 'Invalid grade level' });
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
        return Number.isInteger(wage) ? wage : null;
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

// Extender BusinessManager con funciones API
if (typeof BusinessManager !== 'undefined') {
    Object.assign(BusinessManager, {
        syncedEmployees: Array.isArray(BusinessAPI.currentBusiness?.employees)
            ? [...BusinessAPI.currentBusiness.employees]
            : [],

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
