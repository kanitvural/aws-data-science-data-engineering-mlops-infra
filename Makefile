ifndef env
$(error env is undefined. Usage: make <bootstrap|deploy|destroy> env=<ds|de|mlops|app|llm>)
endif

bootstrap:
	./run.sh bootstrap $(env)

deploy:
	./run.sh deploy $(env)

destroy:
	./run.sh destroy $(env)
