=======================
The permission system

Permissions are a combination of roles and narrowings.
- A team onwer can do anything.
- A team admin can do anything, but assign new admins. An admin can have
that role for a team or a project.
- A manager can do less, and can have it's priviledges attached to a teamd, 
a project or a language.
- A contributor can do less, and can have it's priviledges attached to a teamd,
a project or a language.

The list of permissions for each object can be seen on their models
(e.g. teams.models.Project)).
 
So any set of permissions can be assigned to an entire team, on a project
or a specific language. These are called narrowings. If a user has a permission
team wise, he will end up with a MembershipNarrowing: content team set for that TeamMember
 
What the permission checking done is:
- if owner: can do anything
- Else will check if the permission has narrowing, for team, project then lang 
 
There is a performance hit. In the worst case scenario.
we're running three checks instead of 1. This is fine, because we
are only checking things this way on data writing operations which are a
minority of traffic.

teams.permissions 
=================
Most of the business logic for permissions.

.. automodule:: unisubs.apps.teams.permissions
    
teams.permissions_const    
===========================
Is a somewhat declarative approach to what is allowed
and how rules interact. This is on a stand alone module to avoid issues
with circular dependencies on imports.

.. automodule:: unisubs.apps.teams.permissions_const
=======
=====================

The permission system in Amara is very flexible to allow for the
needs of different teams.  This document will give you a high level overview of
what is possible.  You should read this before trying to understand the source
code.

Overview
--------

Let's start with some language.  In the simplest case, when a user is part of a
team, they can have one of the following roles:

* Contributor
    * Transcribe
    * Translate
    * Assign tasks to themselves
* Manager
    * Review subtitles
    * Approve subtitles
    * Assign tasks to other people
    * Everything that a contributor can do
* Admin
    * Assign new managers
    * Delete subtitles
    * Everything that a manager can do
* Owner
    * Everything

.. note:: This is just an example to give you an idea of how this could work.

A user's role is stored in the ``teams.models.TeamMember`` model which stores a
reference to the user and team objects.

Checking for required permissions
---------------------------------

When you want to check if a certain user has the required privileges to perform
a task, you should use one of the functions in ``teams.permissions``.  For
example, if you'd like to check if a user can approve a video, you could do
something like this:

.. code-block:: python

    from teams.permissions import can_approve

    if can_approve(video, user):
        # Do something that requires the approval permission

.. note:: There is no middleware to attach the current user's privileges to the
    request instance.  Instead, you have explicitly call the necessary
    function whenever you want to verify the user's privileges.

Workflows
---------

A team can choose their own workflow to efficiently manage their videos,
translations and volunteers.  When you are setting up a workflow for your team,
you can decide how certain actions will be performed.  For example:

* Who can join the team?
* Who can and remove videos from the team?
* Who can assign tasks?
* How many tasks a user can have at a time?
* How many days should a user get to complete a task?
* Who can transcribe subtitles?
* Who can translate subtitles?
* Is there a review process?
* Is there an approval process?

So, why should you care?  For example, you don't trust your contributors with
transcription of new videos since it's somewhat difficult.  Therefore, you can
choose to only allow managers and above to transcribe videos and contributors
to only translate videos to different languages.  Or, the quality of the
subtitles is crucial to you and you want to make sure that nothing less than
that ever gets out.  So, you would turn on both the review and approval
process.  This way three sets of eyes will look at the subtitles before it goes
public.
