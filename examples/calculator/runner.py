
def run(context, inputs):
    """
    This is the entrypoint for the automation.
    """
    try:
        num1 = inputs['num1']
        num2 = inputs['num2']
        operation = inputs['operation']
        result = 0

        if operation == "add":
            result = num1 + num2
        elif operation == "subtract":
            result = num1 - num2
        elif operation == "multiply":
            result = num1 * num2
        elif operation == "divide":
            if num2 == 0:
                return {"error": "Cannot divide by zero."}
            result = num1 / num2
        else:
            return {"error": f"Unknown operation: {operation}"}

        return {"result": result}

    except Exception as e:
        return {"error": str(e)}
