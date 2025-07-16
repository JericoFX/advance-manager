# advance-manager

Advanced Business Management System for FiveM QBCore

## Features

- **Dynamic Job Integration**: Automatically reads jobs from QBCore.Shared.Jobs
- **Automatic Permission System**: Boss grades are automatically detected and granted permissions
- **Business Management**: Create and manage businesses with funds tracking
- **Employee System**: Track employees and their wages
- **Flexible Architecture**: Designed to work with any job type

## Installation

1. Place the resource in your `resources/[advanced]` folder
2. Add `ensure advance-manager` to your server.cfg
3. Start your server - database tables will be created automatically

## Commands

### Admin Commands
- `/createbusiness` - Opens interface to create a new business
- `/createbusiness [name] [owner_id] [job_name] [starting_funds]` - Create a new business via command line

### User Commands
- `/businessmenu` - Open business management menu

## Exports

### Server Exports

#### Business Management
- `createBusiness(name, owner, jobName, startingFunds, metadata)` - Create a new business
- `getBusinessById(businessId)` - Get business by ID
- `getBusinessByJob(jobName)` - Get business by job name
- `getBusinessByOwner(citizenId)` - Get all businesses owned by a citizen
- `updateBusinessFunds(businessId, amount, isWithdrawal)` - Add/subtract funds with withdrawal flag
- `setBusinessFunds(businessId, amount)` - Set exact fund amount
- `getBusinessFunds(businessId)` - Get current fund amount
- `hasBusinessPermission(citizenId, businessId, permission)` - Check permissions
- `isBusinessBoss(citizenId, businessId)` - Check if citizen is boss

#### Employee Management
- `getBusinessEmployees(businessId)` - Get all employees for a business (from database)
- `getBusinessEmployeesFromCache(businessId)` - Get all employees for a business (from cache)
- `getEmployeeByBusinessAndCitizen(businessId, citizenId)` - Get specific employee data
- `getAllEmployeesCache()` - Get complete employee cache (GlobalState.BusinessEmployees)
- `isEmployeeOfBusiness(businessId, citizenId)` - Check if citizen is employee of business
- `getEmployeeGrade(businessId, citizenId)` - Get employee's grade/level
- `refreshEmployeeCache(businessId)` - Refresh cache for specific business

## Database Tables

### businesses
- `id` - Business ID (Primary Key)
- `name` - Business name
- `owner` - Owner citizen ID
- `job_name` - Associated job name
- `funds` - Business funds
- `metadata` - Additional business data (JSON)

### business_employees
- `id` - Employee ID (Primary Key)
- `business_id` - Business ID (Foreign Key)
- `citizenid` - Employee citizen ID
- `grade` - Employee grade
- `wage` - Employee wage

## Usage Example

```lua
-- Create a mechanic shop
local success, businessId = exports['advance-manager']:createBusiness(
    'Downtown Mechanics',
    'ABC12345',
    'mechanic',
    50000,
    {location = 'Downtown'}
)

-- Check if player is boss
local isBoss = exports['advance-manager']:isBusinessBoss('ABC12345', businessId)

-- Deposit funds (add money)
exports['advance-manager']:updateBusinessFunds(businessId, 5000, false)

-- Withdraw funds (remove money)
exports['advance-manager']:updateBusinessFunds(businessId, 2000, true)

-- Get employees from cache (fast, no database query)
local employees = exports['advance-manager']:getBusinessEmployeesFromCache(businessId)

-- Check if player is employee of business
local isEmployee = exports['advance-manager']:isEmployeeOfBusiness(businessId, 'ABC12345')

-- Get employee grade
local grade = exports['advance-manager']:getEmployeeGrade(businessId, 'ABC12345')

-- Get specific employee data
local employee = exports['advance-manager']:getEmployeeByBusinessAndCitizen(businessId, 'ABC12345')
if employee then
    print('Employee:', employee.name, 'Grade:', employee.grade, 'Wage:', employee.wage)
end

-- Access complete employee cache (all businesses)
local allEmployees = exports['advance-manager']:getAllEmployeesCache()
for businessId, employees in pairs(allEmployees) do
    print('Business', businessId, 'has', #employees, 'employees')
end
```

## Employee Cache System

The advance-manager includes a high-performance employee cache system that:

- **Loads on startup**: All employees are loaded into GlobalState.BusinessEmployees
- **Auto-updates**: Cache is refreshed automatically when employees are hired, fired, or updated
- **Fast access**: Other resources can access employee data without database queries
- **Real-time sync**: All clients receive updates via GlobalState synchronization

### Cache Structure

```lua
GlobalState.BusinessEmployees = {
    ['1'] = { -- Business ID
        {
            id = 1,
            citizenid = 'ABC12345',
            grade = 2,
            wage = 50,
            name = 'John Doe',
            business_name = 'Downtown Mechanics',
            job_name = 'mechanic',
            last_updated = 1642694400
        }
    }
}
```
