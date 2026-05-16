# Shelter Skill

## Description

I want a skill that:

* Grants an ability called **Shelter.**
* When the **ability** is used, an adjacent target becomes the user's pair up partner

## Tutorial

**Step 1: Turn on pair up**

<span dir="">Open the constants editor and enable the pair up constant</span>.

![shelter1](./images/Shelter-Skill/shelter1.png)

**Step 2: Create an event that does the pairing**

<span dir="">Open the event editor and navigate to global events</span>. In a new event, enter the following code.

~~~
move_unit;{unit2};{unit};normal;stack;no_follow
pair_up;{unit2};{unit}
~~~

<span dir="">Do not set an event trigger. Name the event something like "Shelter"</span>.

**Step 3: Create a shelter item**

<span dir="">Open the item editor and create a shelter item</span>.

![shelter2](./images/Shelter-Skill/shelter2.png)

<span dir="">While you can make the minimum and maximum range whatever you want, this configuration will ensure a system that works like Fates Shelter.</span>.

**Step 4: Create a shelter skill**

<span dir="">Open the skill editor and create a shelter skill</span>.

![shelter3](./images/Shelter-Skill/shelter3.png)

<span dir="">Add a description and skill icon that you like</span>.

**Conclusion**

<span dir="">You're done! Test the skill in a debug map to try it out</span>.