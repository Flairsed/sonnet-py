sfdbcload: ./libs/sfdbcloader.c
	mkdir -p ./libs/compiled
	gcc -fPIC -shared -o ./libs/compiled/sonnet.1.1.6-DEV.0.so ./libs/sfdbcloader.c
