try:
    import verify_email
    print(getattr(verify_email, '__file__', 'no-file'))
except Exception as e:
    print('IMPORT_ERROR:', repr(e))
