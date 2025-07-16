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
- `createBusiness(name, owner, jobName, startingFunds, metadata)` - Create a new business
- `getBusinessById(businessId)` - Get business by ID
- `getBusinessByJob(jobName)` - Get business by job name
- `getBusinessByOwner(citizenId)` - Get all businesses owned by a citizen
- `updateBusinessFunds(businessId, amount)` - Add/subtract funds
- `setBusinessFunds(businessId, amount)` - Set exact fund amount
- `getBusinessFunds(businessId)` - Get current fund amount
- `hasBusinessPermission(citizenId, businessId, permission)` - Check permissions
- `isBusinessBoss(citizenId, businessId)` - Check if citizen is boss

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

-- Update business funds
exports['advance-manager']:updateBusinessFunds(businessId, 5000)
```
