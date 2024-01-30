# di-service-locator

The `di-service-locator` library provides an injection context using a service locator pattern to provide services throughout a codebase.  These services can be developed independantly as reusable, composable components that can depend on other features to provide richer components.

The injection context can be driven from config meaning that the implementations for an app can be changed without having to actually change the code.

There are numerous benefits to this approach including the ability to completely change a project from one cloud provider to another just by changing the config which will detail components such as bucket storage, instrumentation, execution etc.  It can also be used to provide simpler implementations for local execution, taking advantage of the file system and local processes, all without having to change any code.

It is my hope that this approach can become a backbone to our projects and provide a more prescriptive way of developing libraries and solutions in a simple, composable way.  Making future development intuitive and efficient.


## Developing Services
1. Start by abstracting what the service does, what people are going to need the service to do.  Keep the scope small and encapsulated.  Remember that services can be built on top of other services, so try to identify the smallest, reusable pieces
2. Create an interface (abstract base class with only abstract methods defined) for the service methods
3. Write the implementation (or implementations).  The implementations can currently only be instantiated with primitive arguments, although we can improve that in the future.  But, for now, a litle care must be taken with what the implementations require to be instantiated.
4. Write an example of the features config for inclusion in peoples `features.json` files
5. Make everyone aware of your awesome, new service!


## Using Services
Once a service library has been installed into a project accessing the service is trivial.  The service can be obtained statically from a configured ServiceLocator instance by specifying the desired abstraction interface.  An appropriate implementation will be retrieved from the ServiceLocator cache or instantiated and returned if necessary.

```python
from di_service_locator.features import ServiceLocator
from di_service_locator.feature_defs.interfaces import BlobStorage

blob_storage = ServiceLocator.service(BlobStorage)
key = blob_storage.put(data)
```

Note that the code doesn't need to import or even know about the provided implementation.


## Configuring Services
The features injection context needs to be configured.

The preferred mechanism for configuring the context is to use a json file specifying the available features and implementations.
An example of this json file;
```json
{
    "version": 1,
    "features": {
        "blob_storage": {
            "factory": "di_service_locator.feature_defs.blob_storeage.FileBlobStorage",
            "implements": "di_service_locator.feature_defs.interfaces.BlobStorage",
            "args": [],
            "kwargs": {
                "root_path": "/tmp/blobstorage"
            }
        }
    }
}
```
This file needs to be called `features.json` and should be located in the directory from which the application is started or the user home directory in a folder called `.di`.

Additionally a special argument can be specified during the configuration of such services, the `default` argument. This argument must be used if there are multiple definitions for the same factory and you want to force the Service Locator to return a specific  definition.


### Config properties
It is sometimes useful to be able to specify parameters to feature implementations at runtime.  The root path for a file blob storage implementation, for example.  These parameters may be user specific or even contain secrets that should not be checked in.

To facilitate this need the `features.json` file supports property resolution on args and kwargs for a feature.  Properties can be indicated using a `$` prefix.
```json
{
    "version": 1,
    "features": {
        "blob_storage": {
            "factory": "di_service_locator.feature_defs.blob_storeage.FileBlobStorage",
            "implements": "di_service_locator.feature_defs.interfaces.BlobStorage",
            "args": [],
            "kwargs": {
                "root_path": "$STORAGE_ROOT_PATH"
            }
        }
    }
}
```
The property values can be specified via the command line, an environment variable or the project `.env` file.  Properties will be located in order;
* command line overide
* environment variable
* .env file

To specifiy on the command line prefix the property name with `--`;
```bash
python -m my_project.main --STORAGE_ROOT_PATH=/tmp/ds
```

To specify an environment variable;
```bash
export STORAGE_ROOT_PATH=/tmp/ds
python -m my_project.main
```

To specify in a `.env` file add the name and value to the file;
```shell
STORAGE_ROOT_PATH = /tmp/ds
```

### Configuring in code

There is an option to configure the features context in code;

```python
Features.configure({
    "blob_storage": FactoryDefinition(
        fqn_impl_factory="di_service_locator.feature_defs.blob_storage.FileBlobStorage",
        fqn_interface="di_service_locator.feature_defs.interfaces.BlobStorage",
        args=[],
        kwargs={
            "root_path": "/tmp/blobstorage"
        },
    )
})
```
This configuration step needs to be performed before accessing any services and should probably be one of the first things done in an apps entry point.

## How to run locally

Execute `make start-dependencies` in order to start whichever dependencies your project might have. You should always have the base Python image.

Execute `make run` and your application should be running.

Execute `make stop-dependencies` when you no longer need to execute your project.

## How to know which `make` recipes are available

Run `make`

## How to run tests

Run `make test`

## How to run tests with coverage report

Run `make coverage`
