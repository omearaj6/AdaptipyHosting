import os
import json

def generate_problem_with_solution(topic: str, profs: dict) -> dict:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        #topic_prof = float(profs.get(topic, 0.0))

        prompt = f"""
        You are a tutor generating a single Python problem for a student. Their proficiency in each topic ranges from 0-5, where each level introduces ONE new concept. Level X should ONLY teach the concept listed for level X - do NOT skip ahead or introduce future concepts.

        CRITICAL RULES FOR PROBLEM GENERATION:
        1. The problem MUST focus on teaching the EXACT concept listed for the main topic's current level
        2. Do NOT include ANY concepts from levels higher than the student's current proficiency in ANY topic
        3. Do NOT introduce new topics as subtopics - only use topics the student has already encountered (proficiency > 0)
        4. For level 0 problems (first encounter with a topic), keep it EXTREMELY simple - just the bare minimum to demonstrate the concept
        5. Each problem should gradually increase in complexity, but always stay focused on the current level's concept
        6. If you are giving an example of code and output, make sure it is DIFFERENT to what the problem is asking
        7. If the lesson introduces a certain function or concept, tell the student to use that concept in the problem

        Here is the curriculum you MUST follow EXACTLY:

        print_basics:
        0 → print a string literal (e.g., print("Hello"))
           - ONLY teach: how to put text in quotes inside print()
           - Do NOT use: variables, numbers, multiple arguments, concatenation
        1 → print numbers (e.g., print(123))
           - ONLY teach: numbers don't need quotes
           - CRITICAL: Explain the difference between print("123") and print(123)
           - Can reference: level 0 print concepts
        2 → multiple arguments (e.g., print("Hello", "World"))
           - ONLY teach: print() can take multiple items separated by commas
           - Can reference: level 0-1 print concepts
        3 → concatenation (e.g., print("Hello" + " " + "World"))
           - ONLY teach: using + to join strings
           - Can reference: level 0-2 print concepts
        4 → escape characters (e.g., print("Hello\\nWorld"))
           - ONLY teach: \\n, \\t, etc.
           - Can reference: level 0-3 print concepts
        5 → indexing inside print (e.g., print("Hello"[0]))
           - ONLY teach: accessing string characters directly in print
           - Can reference: level 0-4 print concepts

        variables:
        0 → assign string and print
           - ONLY teach: variable = "value" and print(variable)
           - Do NOT use: numbers, reassignment, multiple variables
        1 → assign numbers
           - ONLY teach: variable = 123
           - Can reference: level 0 variables, level 0-1 print_basics if needed
        2 → reassign variable
           - ONLY teach: changing a variable's value
           - Can reference: level 0-1 variables
        3 → multi-assignment (e.g., a, b = 1, 2)
           - ONLY teach: assigning multiple variables at once
           - Can reference: level 0-2 variables
        4 → transform before printing (e.g., str(123) or int("123"))
           - ONLY teach: type conversion functions
           - Can reference: level 0-3 variables
        5 → combine multiple variables in expressions
           - ONLY teach: using multiple variables together
           - Can reference: level 0-4 variables

        operators:
        0 → + - * /
           - ONLY teach: basic arithmetic on numbers
           - CRITICAL: Do NOT use variables unless variables proficiency > 0
           - Example: print(5 + 3) NOT a + b
        1 → precedence (order of operations)
           - ONLY teach: how brackets and operator precedence work
           - Can reference: level 0 operators
        2 → // % **
           - ONLY teach: floor division, modulo, exponent
           - Can reference: level 0-1 operators
        3 → floats
           - ONLY teach: decimal numbers and float arithmetic
           - Can reference: level 0-2 operators
        4 → multi-step expressions
           - ONLY teach: combining multiple operations (MAKE SURE EXPECTED OUTPUT IS CORRECT)
           - Can reference: level 0-3 operators
        5 → combine with variables
           - ONLY teach: using operators with variables
           - Can ONLY use variables if variables proficiency > 0
           - Can reference: level 0-4 operators

        strings:
        0 → len()
           - ONLY teach: len() function on strings
           - CRITICAL: Do NOT use variables unless variables proficiency > 0
           - Example: print(len("hello")) NOT text = "hello"; print(len(text))
        1 → indexing
           - ONLY teach: accessing characters by position [0], [1], etc.
           - CRITICAL: Explain that indexing starts at 0
           - Can reference: level 0 strings
        2 → slicing
           - ONLY teach: [start:end] to get substrings
           - Can reference: level 0-1 strings
        3 → negative indexing
           - ONLY teach: using negative numbers to index from the end
           - Can reference: level 0-2 strings
        4 → string methods (.upper(), .lower(), .count(), etc.)
           - ONLY teach: built-in string methods
           - Can reference: level 0-3 strings
        5 → multiple operations combined
           - ONLY teach: combining different string operations
           - Can reference: all previous string levels

        lists:
        0 → create and print
           - ONLY teach: list = [1, 2, 3] and print(list)
           - Do NOT use: indexing, slicing, modifications, nested lists
        1 → indexing
           - ONLY teach: accessing list elements by position [0], [1]
           - Can reference: level 0 lists
        2 → slicing
           - ONLY teach: [start:end] to get sublists
           - Can reference: level 0-1 lists
        3 → modify elements
           - ONLY teach: changing list elements (list[0] = new_value)
           - Can reference: level 0-2 lists
        4 → nested lists
           - ONLY teach: lists inside lists and accessing them
           - Can reference: level 0-3 lists
        5 → list comprehension
           - ONLY teach: [expression for item in list]
           - Can ONLY use if for_loops proficiency >= 2
           - Can reference: all previous list levels

        conditionals:
        0 → if
           - ONLY teach: simple if statement with one condition
           - Do NOT use: else, elif, boolean operators
           - Example: if x > 5: print("big")
        1 → if/else
           - ONLY teach: if and else together
           - Can reference: level 0 conditionals
        2 → elif
           - ONLY teach: adding elif for multiple conditions
           - Can reference: level 0-1 conditionals
        3 → boolean operators (and, or, not)
           - ONLY teach: combining conditions
           - Can reference: level 0-2 conditionals
        4 → nested conditionals
           - ONLY teach: if statements inside if statements
           - Can reference: level 0-3 conditionals
        5 → complex logic
           - ONLY teach: combining all conditional concepts
           - Can reference: all previous conditional levels

        for_loops:
        0 → range(n)
           - ONLY teach: for i in range(n): print(i)
           - Do NOT use: lists, custom ranges, accumulators, nested loops
           - Can iterate through: simple numbers, or characters of a string (if strings > 0)
        1 → custom range (start, stop, step)
           - ONLY teach: range(start, stop) and range(start, stop, step)
           - Can reference: level 0 for_loops
        2 → iterate list
           - ONLY teach: for item in list: print(item)
           - Can ONLY use if lists proficiency > 0
           - Can reference: level 0-1 for_loops
        3 → accumulator pattern
           - ONLY teach: building a result (sum, count, string building)
           - Can reference: level 0-2 for_loops
        4 → nested loops
           - ONLY teach: loops inside loops
           - Can reference: level 0-3 for_loops
        5 → conditional filtering
           - ONLY teach: if statements inside loops
           - Can reference: level 0-4 for_loops and conditionals

        while_loops:
        0 → counter loop
           - ONLY teach: i = 0; while i < n: print(i); i += 1
           - CRITICAL: Keep it SIMPLE - just counting up or down
           - Do NOT use: complex conditions, accumulators, nested logic
           - Example: Print numbers 1 to 5 using a counter
        1 → condition-based
           - ONLY teach: while with a boolean condition (not just counter)
           - Can reference: level 0 while_loops
        2 → accumulator pattern
           - ONLY teach: building a result during the loop
           - Can reference: level 0-1 while_loops
        3 → nested logic
           - ONLY teach: more complex loop bodies
           - Can reference: level 0-2 while_loops
        4 → sentinel logic
           - ONLY teach: loops that run until a sentinel value
           - Can reference: level 0-3 while_loops
        5 → complex condition
           - ONLY teach: while with multiple conditions
           - Can reference: all previous while_loops levels

        CRITICAL SUBTOPIC RULES:
        - Only include a subtopic if its proficiency > 0
        - NEVER use a topic as a subtopic if it hasn't been introduced yet
        - For level 0 problems, use ZERO subtopics - focus ONLY on the new concept
        - For level 1 problems, you may use ONE simple subtopic if appropriate
        - Gradually increase subtopics as levels increase, but always keep the main focus on the current level's concept

        Here is the student’s proficiency levels in all topics:
        {json.dumps(profs, indent=2)}

        The problem you are generating is based on this main topic: {topic}
        The student is at level {int(float(profs.get(topic, 0)))} in this topic.

        BEFORE GENERATING, CHECK:
        1. Does this problem ONLY teach the concept listed for level {int(float(profs.get(topic, 0)))} of {topic}?
        2. Have I avoided introducing ANY topics with proficiency 0 as subtopics?
        3. Is the complexity appropriate for this level? (Level 0 should be VERY simple)
        4. Does the lesson clearly explain the ONE new concept being taught?
        5. Is the expected_output exactly what a correct solution would print?
        6. Is the expected_output obtainable from the PROBLEM text? (NOT the lesson text)

        You must output in EXACTLY this JSON format:
        {{
          "problem": "...",
          "explanation": "...",
          "expected_output": "...",
          "general_hints": ["..."],
          "subtopics_used": ["..."],
          "subtopic_hints": {{ "subtopic": "hint" }},
          "lesson": "..."
        }}

        Definitions:
        - "problem": The Python problem to solve. Use concrete values, no input().
        - "explanation": Clarify the problem step by step.
        - "expected_output": EXACT output the correct solution prints. Just the output, no extra text.
        - "general_hints": 2 hints about the main topic concept.
        - "subtopics_used": Array of subtopics included (only those with proficiency > 0).
        - "subtopic_hints": Dictionary of hints for each subtopic used.
        - "lesson": Explain the ONE new concept for this level. Include a short code example with input/output.

        Remember: Return ONLY the JSON. No markdown, no extra text.
        """


        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Return strict JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )

        raw = (response.choices[0].message.content or "").strip()
        data = json.loads(raw)

        return {
            "problem": data.get("problem", ""),
            "expected_output": data.get("expected_output", ""),
            "explanation": data.get("explanation", ""),
            "general_hints": data.get("general_hints", []),
            "subtopics_used": data.get("subtopics_used", []),
            "subtopic_hints": data.get("subtopic_hints", {}),
            "lesson": data.get("lesson", ""),
        }

    except Exception:

        p, e = (
         (f"Write a short Python program about {topic} that prints a simple result.", "OK")
        )

        lesson = ""
        if float(profs.get(topic, 0.0)) == 0.0:
            lesson = "Intro: try printing a simple value first (e.g., print(1)) and then build from there."

        return {
            "problem": p,
            "expected_output": e,
            "explanation": "",
            "general_hints": [],
            "subtopics_used": [],
            "subtopic_hints": {},
            "lesson": lesson,
        }