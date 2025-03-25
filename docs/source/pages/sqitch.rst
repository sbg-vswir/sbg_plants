==============================
Version Control For SBG Plants
==============================

This section is intended for database administrators responsible for altering the database schema.

Currently, the database repository is set up with **Sqitch**, an open-source version control tool specifically designed
for managing **SQL database schema changes**. We are using Sqitch to track schema migrations, which are incremental changes 
to the database structure.

How Sqitch Works
----------------

With Sqitch, the process for making schema changes is straightforward:

1. **Deployments**: When you want to make a change to the schema, you write the change in an SQL script. This is known as a **deployment** script. 
Each deployment is tracked and versioned by Sqitch.
  
2. **Verification**: You can optionally create a **verification script**. This script will run before the deployment 
is made live to ensure that any preconditions or necessary checks are met. The deployment will only proceed if the verification script succeeds.

3. **Revert Scripts**: You can also create a **revert script** to undo a deployment if necessary. 
This is important for rollback scenarios, allowing you to revert to a previous schema version if the deployment doesn't work as expected.

At this time, we are primarily using Sqitch to track **schema migrations**, not data migrations or other changes.

Connecting to the Database From Your Local Machine
==================================================

For the security purposes, you cannot connect directly to the database from your local machine. You have to use a bastion or jump instance.

The following command can be run in a terminal to set up a tunnel to access the database locally.

::
    
    ssh -i <path_to_private_key> -L 5432:<database_enbdpoint>:5432 ubuntu@<bastion_host_ip> -N

Once this command is running, in a fresh terminal the database is accessible via localhost port 5432.

To test your connection with sqitch run the following:

::
    
    sqitch verify db:pg://<your-username>:<your_password>@localhost/sbgplants

A suggestion is to put the database uri in a .env file

In your .env file:

::

    uri=db:pg://<your-username>:<your_password>@localhost/sbgplants


Then:

::
    
    source .env
    sqitch verify $uri

How to Use Sqitch (Basic Workflow)
-----------------------------------

1. **Create a Deployment Script**: Write a migration (e.g., creating a table, altering a column) in a SQL file.
2. **Verify the Deployment (sqitch verify)**: If necessary, write a verification script that checks prerequisites (e.g., dependencies, version checks) before the deployment.
3. **Deploy the Change (sqitch deploy)**: Run the deployment script to apply the schema change to the database.
4. **Revert if Necessary (sqitch revert [TARGET])**: If you need to undo a change, run the revert script to roll back the schema to its previous state. The target is the version you would like to undo. (reverts the version before target)


`Official Sqitch documentation <https://sqitch.org/docs/>`_
